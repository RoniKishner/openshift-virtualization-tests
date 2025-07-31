import os
import subprocess
import json
from github import Github
from typing import List, Dict, Tuple

def get_changed_files() -> List[Dict]:
    """Get list of changed files between base and head branch."""
    base_ref = os.environ['GITHUB_BASE_REF']
    diff_command = f"git diff --name-status {base_ref}...HEAD"
    result = subprocess.run(diff_command.split(), capture_output=True, text=True)
    changes = []
    
    for line in result.stdout.splitlines():
        status, *file_path = line.split()
        file_path = file_path[0]
        changes.append({
            'status': status,
            'path': file_path
        })
    
    return changes

def is_simple_change(file_path: str) -> bool:
    """
    Determine if a file change is simple (constants or name changes only).
    Returns True if the change is simple, False otherwise.
    """
    base_ref = os.environ['GITHUB_BASE_REF']
    
    # Get the diff for this file
    diff_command = f"git diff {base_ref}...HEAD -- {file_path}"
    result = subprocess.run(diff_command.split(), capture_output=True, text=True)
    diff = result.stdout

    # Skip if file is new or deleted
    if not os.path.exists(file_path) or diff.startswith('diff --git a/' + file_path + ' /dev/null'):
        return False

    # Read the file content
    with open(file_path, 'r') as f:
        content = f.read()

    # Simple heuristics for simple changes:
    # 1. Only constant changes (strings, numbers)
    # 2. Only variable/function name changes
    # 3. No structural changes (indentation, new blocks)
    
    # Count lines changed
    added = len([l for l in diff.splitlines() if l.startswith('+')])
    removed = len([l for l in diff.splitlines() if l.startswith('-')])
    
    # If too many changes, consider it complex
    if added + removed > 20:
        return False
        
    # Check for structural changes
    structural_indicators = [
        'class ',
        'def ',
        'import ',
        'from ',
        '@',  # decorators
        'if ',
        'for ',
        'while ',
        'try:',
        'except',
        'finally:',
    ]
    
    for line in diff.splitlines():
        if line.startswith('+') or line.startswith('-'):
            # Check for structural changes
            if any(indicator in line for indicator in structural_indicators):
                return False
            
            # Check for indentation changes
            if line[1:].startswith('    '):
                return False

    return True

def create_branch_and_pr(files: List[Dict]) -> None:
    """Create a new branch with simple changes and submit a PR."""
    g = Github(os.environ['GITHUB_TOKEN'])
    repo = g.get_repo(os.environ['REPO_NAME'])
    base_branch = os.environ['GITHUB_BASE_REF']
    pr_number = os.environ['PR_NUMBER']
    
    # Create new branch
    timestamp = subprocess.check_output(['date', '+%Y%m%d-%H%M%S']).decode().strip()
    new_branch = f"simple-changes-{timestamp}"
    
    # Create and checkout new branch
    subprocess.run(['git', 'checkout', '-b', new_branch])
    
    # Reset to base branch
    subprocess.run(['git', 'reset', '--hard', base_branch])
    
    # Apply simple changes
    for file in files:
        if file['status'] == 'M':  # Modified files only
            # Cherry pick changes for this file
            subprocess.run(['git', 'checkout', 'HEAD', file['path']])
    
    # Commit changes
    subprocess.run(['git', 'add', '.'])
    subprocess.run(['git', 'commit', '-m', 'Simple changes: constants and name updates'])
    
    # Push branch
    subprocess.run(['git', 'push', 'origin', new_branch])
    
    # Create PR
    original_pr = repo.get_pull(int(pr_number))
    title = f"Simple changes from #{pr_number}"
    body = f"""This PR contains simple changes extracted from #{pr_number}.
    
These changes are limited to:
- Constant value updates
- Variable/function name changes
- No structural changes

Original PR: #{pr_number}
"""
    
    repo.create_pull(
        title=title,
        body=body,
        base=base_branch,
        head=new_branch
    )

def main():
    # Get all changed files
    changed_files = get_changed_files()
    
    # Filter for simple changes
    simple_changes = [
        file for file in changed_files
        if is_simple_change(file['path'])
    ]
    
    # If we found simple changes, create a PR
    if simple_changes:
        create_branch_and_pr(simple_changes)

if __name__ == '__main__':
    main() 