import os
import sys

def package_repo(root_dir, output_file, ignore_dirs=None):
    if ignore_dirs is None:
        ignore_dirs = {'.git', '__pycache__', '.DS_Store', 'node_modules', 'dist', 'build'}
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Repository Analysis: {os.path.abspath(root_dir)}\n")
        f.write("## Directory Structure\n\n")
        
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            level = root.replace(root_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            f.write(f"{indent}- {os.path.basename(root)}/\n")
            sub_indent = ' ' * 4 * (level + 1)
            for file in files:
                if file not in ignore_dirs:
                    f.write(f"{sub_indent}- {file}\n")
        
        f.write("\n---\n\n")
        f.write("## File Contents\n\n")
        
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file in ignore_dirs:
                    continue
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, root_dir)
                
                # Simple text file check (can be improved)
                if file.endswith(('.md', '.py', '.js', '.ts', '.txt', '.json', '.yml', '.yaml', '.html', '.css')):
                    f.write(f"### File: {rel_path}\n")
                    f.write("```\n")
                    try:
                        with open(file_path, 'r', encoding='utf-8') as content_f:
                            f.write(content_f.read())
                    except Exception as e:
                        f.write(f"Error reading file: {e}\n")
                    f.write("\n```\n\n")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    output = sys.argv[2] if len(sys.argv) > 2 else "repo_context.txt"
    package_repo(target, output)
    print(f"Successfully packaged {target} into {output}")
