import os
import subprocess
import json
from github import Github
from typing import List, Dict, Tuple

DIFF_COMMAND = f"git diff --name-status origin/{os.environ['BASE_REF']}..origin/{os.environ['HEAD_REF']}"
PR_NUMBER = os.environ['PR_NUMBER']

def get_changed_files() -> List[Dict]:
    """Get list of changed files between base and head branch."""
    result = subprocess.run(DIFF_COMMAND.split(), capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error running git diff:\nstdout: {result.stdout}\nstderr: {result.stderr}")

    return [
        {'status': line.split()[0], 'path': line.split()[1]}
        for line in result.stdout.splitlines()
        if line.strip()
    ]

def is_simple_change(file_path: str) -> bool:
    """
    Determine if a file change is simple (constants or name changes only).
    Returns True if the change is simple, False otherwise.
    """
    file_diff_command = f"{DIFF_COMMAND} -- {file_path}"
    result = subprocess.run(file_diff_command.split(), capture_output=True, text=True)
    diff = result.stdout

    # Skip if file is new or deleted
    if not os.path.exists(file_path) or diff.startswith('diff --git a/' + file_path + ' /dev/null'):
        return False

    # Read the file content
    with open(file_path, 'r') as f:
        content = f.read()

    # Count lines changed
    diff_lines = diff.splitlines()
    added = sum(1 for l in diff_lines if l.startswith('+'))
    removed = sum(1 for l in diff_lines if l.startswith('-'))
    
    # If too many changes, consider it complex
    if added + removed > 20:
        return False
        
    # Check for structural changes
    structural_indicators = [
        'class ', 'def ', 'import ', 'from ', '@',  # decorators
        'if ', 'for ', 'while ', 'try:', 'except', 'finally:'
    ]
    
    # Check each changed line for structural changes or indentation
    changed_lines = [line for line in diff_lines if line.startswith('+') or line.startswith('-')]
    return not any(
        indicator in line or line[1:].startswith('    ')
        for line in changed_lines
        for indicator in structural_indicators
    )

def create_branch_and_pr(files: List[Dict]) -> None:
    """Create a new branch with simple changes and submit a PR."""
    g = Github(os.environ['GITHUB_TOKEN'])
    if not g:
        print("Failed to initialize Github client")
        return
        
    repo = g.get_repo(os.environ['REPO_NAME'])
    # Create new branch
    timestamp = subprocess.check_output(['date', '+%Y%m%d-%H%M%S']).decode().strip()
    new_branch = f"simple-changes-{timestamp}"
    
    # Create and checkout new branch
    subprocess.run(['git', 'checkout', '-b', new_branch])
    
    # Reset to base branch
    subprocess.run(['git', 'reset', '--hard', os.environ['BASE_REF']])
    
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
    original_pr = repo.get_pull(int(PR_NUMBER))
    title = f"Simple changes from #{PR_NUMBER}"
    body = f"""This PR contains simple changes extracted from #{PR_NUMBER}.
    
These changes are limited to:
- Constant value updates
- Variable/function name changes
- No structural changes

Original PR: #{PR_NUMBER}
"""
    
    repo.create_pull(
        title=title,
        body=body,
        base={os.environ['BASE_REF']},
        head=new_branch
    )

def main():
    changed_files = get_changed_files()
    for file in changed_files:
        print(f"Status: {file['status']} - File: {file['path']}")

    simple_changes = [file for file in changed_files if is_simple_change(file['path'])]
    
    if simple_changes:
        create_branch_and_pr(simple_changes)

if __name__ == '__main__':
    main() 