import os


def get_sql_cipher_key(file_path: str):
    if not file_path or not os.path.exists(file_path):
        print(f"Error: sqlcipher key file not found: {file_path}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('SQLCipherKey='):
                    return line.split('=', 1)[1]
    except Exception as e:
        print(f"Error reading sqlcipher key file: {e}")

    return None
