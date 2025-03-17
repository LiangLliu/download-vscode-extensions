import requests
import os
import concurrent.futures
from tqdm import tqdm
import sys

def load_extensions(file_path='extensions.txt'):
    extensions = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                if '=' in line:
                    ext_id, version = line.split('=', 1)
                else:
                    ext_id, version = line, 'latest'
                extensions.append((ext_id.strip(), version.strip()))
    return extensions

def prepare_directories():
    os.makedirs('extensions', exist_ok=True)
    os.makedirs('errors', exist_ok=True)

def file_exists(extension_id, version):
    final_file = f"extensions/{extension_id.replace('.', '-')}-{version}.vsix"
    return os.path.exists(final_file)

def download_vscode_extension(extension_id, version='latest'):
    try:
        publisher, ext_name = extension_id.split('.')
    except ValueError:
        return f"Invalid extension id: {extension_id}"

    final_file = f"extensions/{extension_id.replace('.', '-')}-{version}.vsix"
    temp_file = final_file + ".downloading"  # 临时文件名

    if os.path.exists(final_file):
        return f"Skipped: {final_file} (Already exists)"

    url = f"https://marketplace.visualstudio.com/_apis/public/gallery/publishers/{publisher}/vsextensions/{ext_name}/{version}/vspackage"
    response = requests.get(url, allow_redirects=True, stream=True)

    if response.status_code == 200:
        total_size = int(response.headers.get('content-length', 0))
        with open(temp_file, 'wb') as file:
            with tqdm(
                desc=extension_id, total=total_size, unit='B', unit_scale=True, leave=True
            ) as progress_bar:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
                        progress_bar.update(len(chunk))

        os.rename(temp_file, final_file)
        return f"Downloaded: {final_file}"

    elif response.status_code == 500:
        return f"Failed to download {extension_id}: resource not found"
    elif response.status_code == 429:
        with open(f"errors/{extension_id}-error.txt", 'a') as file:
            file.write(f"{response.text}\n")
        return f"Failed to download {extension_id}: rate limited, retry after 5 minutes"
    else:
        with open(f"errors/{extension_id}-error.txt", 'a') as file:
            file.write(f"{response.text}\n")
        return f"Failed to download {extension_id}: HTTP {response.status_code}"

def main():
    extensions = load_extensions()
    prepare_directories()
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        future_to_ext = {
            executor.submit(download_vscode_extension, ext_id, version): (ext_id, version)
            for ext_id, version in extensions
            if not file_exists(ext_id, version)
        }
        try:
            for future in concurrent.futures.as_completed(future_to_ext):
                ext_id, version = future_to_ext[future]
                try:
                    result = future.result()
                    print(result)
                except Exception as exc:
                    print(f"{ext_id} (version {version}) generated an exception: {exc}")
        except KeyboardInterrupt:
            print("\nCtrl+C pressed. Cancelling pending tasks...")
            for future in future_to_ext:
                future.cancel()
            executor.shutdown(wait=False)
            print("Cancelled.")
            sys.exit(1)

if __name__ == '__main__':
    main()