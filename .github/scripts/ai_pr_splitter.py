import os
import sys
import google.generativeai as genai
from github import Github, Auth
import subprocess
import json
import re

def get_pr_files(g, repo_name, pr_number):
    """Get the files changed in the PR"""
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(int(pr_number))
    return list(pr.get_files())

def get_file_content_from_pr(file):
    """Get the content of a file from PR"""
    try:
        if hasattr(file, 'patch'):
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file.filename), exist_ok=True)
            # Write the file content
            with open(file.filename, 'w') as f:
                f.write(file.patch)
            return True
        return False
    except Exception as e:
        print(f"Error writing file {file.filename}: {e}")
        return False

def create_new_branch(base_branch, new_branch_name):
    """Create a new branch from base branch"""
    try:
        # Make sure we have the latest base branch
        subprocess.run(['git', 'fetch', 'origin', base_branch], check=True)
        
        # Try to delete the branch locally if it exists
        subprocess.run(['git', 'branch', '-D', new_branch_name], check=False)
        
        # Try to delete the branch remotely if it exists
        subprocess.run(['git', 'push', 'origin', '--delete', new_branch_name], check=False)
        
        # Checkout the base branch
        subprocess.run(['git', 'checkout', base_branch], check=True)
        
        # Create and checkout new branch
        subprocess.run(['git', 'checkout', '-b', new_branch_name], check=True)
        print(f"Created new branch: {new_branch_name} from {base_branch}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating branch: {str(e)}")
        raise

def commit_changes(files, commit_message):
    """Commit specified files with given message"""
    try:
        # First create/update the files
        files_created = False
        for file in files:
            if get_file_content_from_pr(file):
                files_created = True
                subprocess.run(['git', 'add', file.filename], check=True)
        
        # Only commit if files were created/modified
        if files_created:
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            print(f"Committed changes with message: {commit_message}")
        else:
            print("No changes to commit")
            
    except subprocess.CalledProcessError as e:
        print(f"Error committing changes: {str(e)}")
        raise

def push_branch(branch_name):
    """Push the branch to remote"""
    try:
        # Force push to handle cases where branch exists
        subprocess.run(['git', 'push', '-f', 'origin', branch_name], check=True)
        print(f"Pushed branch: {branch_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error pushing branch: {str(e)}")
        raise

def create_pull_request(g, repo_name, title, body, head, base):
    """Create a new pull request"""
    try:
        repo = g.get_repo(repo_name)
        # Wait a bit for GitHub to register the pushed branch
        import time
        time.sleep(5)
        
        # Create the pull request
        pr = repo.create_pull(
            title=title,
            body=body,
            head=head,  # Should be in format: 'owner:branch_name'
            base=base
        )
        print(f"Created PR: {pr.html_url}")
        return pr
    except Exception as e:
        print(f"Error creating PR: {str(e)}")
        raise

def clean_markdown_response(response_text):
    """Clean markdown formatting from response text"""
    # Remove markdown code block if present
    clean_text = re.sub(r'^```json\n|\n```$', '', response_text.strip())
    return clean_text

def analyze_changes_with_gemini(files):
    """Use Gemini to analyze changes and suggest how to split them"""
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        
        # Use the latest Gemini Pro model
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

        # Prepare the files data for Gemini
        files_data = []
        for file in files:
            if hasattr(file, 'patch'):
                files_data.append({
                    'filename': file.filename,
                    'patch': file.patch
                })

        prompt = f"""
        Analyze these file changes and suggest how to split them into 2 logical, smaller pull requests.
        The split should make sense from a code review perspective.
        Files to analyze: {json.dumps(files_data, indent=2)}
        
        Return your response in this JSON format:
        {{
            "pr1": {{
                "files": ["list", "of", "filenames"],
                "title": "PR title",
                "description": "PR description"
            }},
            "pr2": {{
                "files": ["list", "of", "filenames"],
                "title": "PR title",
                "description": "PR description"
            }}
        }}
        
        Return ONLY the JSON, without any markdown formatting or additional text.
        """

        response = model.generate_content(prompt)
        try:
            if response.text:
                # Clean the response text before parsing JSON
                clean_response = clean_markdown_response(response.text)
                print("Cleaned response:", clean_response)
                return json.loads(clean_response)
            else:
                print("Empty response from Gemini")
                return None
        except Exception as e:
            print("Error parsing Gemini response:", response.text if hasattr(response, 'text') else 'No response text')
            print("Error details:", str(e))
            return None
            
    except Exception as e:
        print("Error in Gemini API call:", str(e))
        return None

def main():
    # Get environment variables
    github_token = os.getenv('GITHUB_TOKEN')
    base_ref = os.getenv('BASE_REF')
    head_ref = os.getenv('HEAD_REF')
    pr_number = os.getenv('PR_NUMBER')
    repo_name = os.getenv('REPO_NAME')
    repo_owner = os.getenv('REPO_OWNER')

    if not all([github_token, base_ref, head_ref, pr_number, repo_name, repo_owner]):
        print("Missing required environment variables")
        sys.exit(1)

    print(f"Base ref: {base_ref}")
    print(f"Head ref: {head_ref}")
    print(f"PR number: {pr_number}")
    print(f"Repo: {repo_owner}/{repo_name}")

    # Initialize GitHub client with proper authentication
    auth = Auth.Token(github_token)
    g = Github(auth=auth)

    try:
        # Get files from original PR
        files = get_pr_files(g, repo_name, pr_number)
        
        if not files:
            print("No files found in PR")
            sys.exit(1)
            
        print(f"Found {len(files)} files in PR")

        # Analyze changes with Gemini
        split_suggestion = analyze_changes_with_gemini(files)
        if not split_suggestion:
            print("Failed to get valid split suggestion from Gemini")
            sys.exit(1)

        created_prs = []

        # Create and push first PR
        pr1_branch = f"{head_ref}-split-1"
        create_new_branch(base_ref, pr1_branch)
        pr1_files = [f for f in files if f.filename in split_suggestion['pr1']['files']]
        if pr1_files:
            commit_changes(pr1_files, split_suggestion['pr1']['title'])
            push_branch(pr1_branch)
            pr1 = create_pull_request(
                g, repo_name,
                split_suggestion['pr1']['title'],
                split_suggestion['pr1']['description'],
                f"{repo_owner}:{pr1_branch}",  # Include owner in head
                base_ref
            )
            created_prs.append(pr1)
        else:
            print("No files for PR1")

        # Create and push second PR
        pr2_branch = f"{head_ref}-split-2"
        create_new_branch(base_ref, pr2_branch)
        pr2_files = [f for f in files if f.filename in split_suggestion['pr2']['files']]
        if pr2_files:
            commit_changes(pr2_files, split_suggestion['pr2']['title'])
            push_branch(pr2_branch)
            pr2 = create_pull_request(
                g, repo_name,
                split_suggestion['pr2']['title'],
                split_suggestion['pr2']['description'],
                f"{repo_owner}:{pr2_branch}",  # Include owner in head
                base_ref
            )
            created_prs.append(pr2)
        else:
            print("No files for PR2")

        # Add comment to original PR with links to new PRs only if PRs were created
        if created_prs:
            repo = g.get_repo(repo_name)
            original_pr = repo.get_pull(int(pr_number))
            comment = "Split this PR into smaller PRs:\n"
            for pr in created_prs:
                comment += f"{pr.number}. {pr.title} - {pr.html_url}\n"
            original_pr.create_issue_comment(comment)
        
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        sys.exit(1)
    finally:
        g.close()

if __name__ == "__main__":
    main() 