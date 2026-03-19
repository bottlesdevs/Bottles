import os
import sys

# Add Bottles path to sys.path to resolve imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bottles.fvs.repo import FVSRepo
from bottles.fvs.exceptions import FVSNothingToCommit

def main():
    repo_path = "/tmp/fvs-test-py"
    if not os.path.exists(repo_path):
        os.makedirs(repo_path)
    
    print(f"Initializing FVSRepo at {repo_path}")
    repo = FVSRepo(repo_path)
    
    print(f"Has no states: {repo.has_no_states}")
    
    file_path = os.path.join(repo_path, "test.txt")
    with open(file_path, "w") as f:
        f.write("test content 1\n")
        
    print("Committing 'First state'")
    repo.commit("First state")
    
    print(f"Active state ID: {repo.active_state_id}")
    first_state_id = repo.active_state_id
    print(f"Num states: {len(repo.states)}")
    
    with open(file_path, "w") as f:
        f.write("test content 2\n")
        
    print("Committing 'Second state'")
    repo.commit("Second state")
    print(f"Num states: {len(repo.states)}")
    
    print(f"Restoring {first_state_id}")
    repo.restore_state(first_state_id)
    
    with open(file_path, "r") as f:
        content = f.read()
    print(f"Content after restore: {content.strip()}")
    assert content.strip() == "test content 1"

if __name__ == "__main__":
    main()
