import os

def find_cargo():
    search_paths = [
        os.path.expanduser("~\\.cargo\\bin\\cargo.exe"),
        "C:\\Program Files\\Rust\\bin\\cargo.exe",
        "C:\\Program Files (x86)\\Rust\\bin\\cargo.exe",
    ]
    for path in search_paths:
        if os.path.exists(path):
            print(f"Found cargo at: {path}")
            return path
            
    print("Cargo.exe not found in standard paths. Searching user folder...")
    user_home = os.path.expanduser("~")
    for root, dirs, files in os.walk(user_home):
        # Limit search depth for speed
        if root.count(os.sep) - user_home.count(os.sep) > 3:
            del dirs[:] # Don't go deeper than 3 levels
            continue
            
        if "cargo.exe" in files:
            full_path = os.path.join(root, "cargo.exe")
            print(f"Found cargo at: {full_path}")
            return full_path
            
    print("Cargo not found.")
    return None

if __name__ == "__main__":
    find_cargo()
