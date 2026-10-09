
import os
import zipfile
import datetime

def zip_project():
    # Exclude these directories/files to keep size small
    EXCLUDE_DIRS = {
        '.venv', '.venv_old_20251029132201', '__pycache__', '.git', 
        '.idea', '.vscode', 'build', 'dist', 'logs', 'web_ui', 'web_api', 'seed'
    }
    EXCLUDE_EXTS = {'.pyc', '.pyo', '.pyd', '.DS_Store', '.zip', '.rar', '.7z'}
    
    # Files to definitely include
    # We will walk the directory, so this is handled automatically.
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    zip_filename = f"YKS_LGS_Project_Transfer_{timestamp}.zip"
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"Zipping project to: {zip_filename}")
    print("Excluding folders:", EXCLUDE_DIRS)
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(current_dir):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in EXCLUDE_EXTS:
                    continue
                if file == zip_filename:
                    continue
                    
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, current_dir)
                
                print(f"Adding: {arcname}")
                zipf.write(file_path, arcname)
                
    print(f"\nSUCCESS! Created {zip_filename}")
    print(f"Size: {os.path.getsize(zip_filename) / (1024*1024):.2f} MB")
    print("Transfer this file to Windows.")

if __name__ == "__main__":
    zip_project()
