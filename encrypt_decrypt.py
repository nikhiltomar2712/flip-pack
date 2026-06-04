#!/usr/bin/env python3
"""
Encrypt/Decrypt - AES encryption/decryption for sensitive files
"""

import os
import sys
import argparse
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64

class FileEncryptor:
    SALT_SIZE = 16
    IV_SIZE = 16
    KEY_SIZE = 32  # AES-256
    PBKDF2_ITERATIONS = 100000
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def encrypt_file(self, input_file: str, password: str, output_file: str = None) -> str:
        """Encrypt a file using AES-256-CBC"""
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")
        
        if output_file is None:
            output_path = input_path.with_suffix(input_path.suffix + '.enc')
        else:
            output_path = Path(output_file)
        
        # Generate random salt and IV
        salt = os.urandom(self.SALT_SIZE)
        iv = os.urandom(self.IV_SIZE)
        
        # Derive key
        key = self._derive_key(password, salt)
        
        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # Read and encrypt file
        with open(input_path, 'rb') as infile:
            plaintext = infile.read()
            
            # Add PKCS7 padding
            padding_length = 16 - (len(plaintext) % 16)
            plaintext += bytes([padding_length]) * padding_length
            
            ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # Write encrypted file with salt and IV prepended
        with open(output_path, 'wb') as outfile:
            outfile.write(salt)
            outfile.write(iv)
            outfile.write(ciphertext)
        
        print(f"✅ Encrypted: {input_file} -> {output_path}")
        print(f"   Original size: {input_path.stat().st_size:,} bytes")
        print(f"   Encrypted size: {output_path.stat().st_size:,} bytes")
        
        return str(output_path)
    
    def decrypt_file(self, input_file: str, password: str, output_file: str = None) -> str:
        """Decrypt a file encrypted with encrypt_file"""
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")
        
        # Read salt, IV, and ciphertext
        with open(input_path, 'rb') as infile:
            salt = infile.read(self.SALT_SIZE)
            iv = infile.read(self.IV_SIZE)
            ciphertext = infile.read()
        
        # Derive key
        key = self._derive_key(password, salt)
        
        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # Decrypt
        try:
            plaintext_padded = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remove PKCS7 padding
            padding_length = plaintext_padded[-1]
            if padding_length > 16:
                raise ValueError("Invalid padding")
            plaintext = plaintext_padded[:-padding_length]
        except Exception as e:
            raise ValueError(f"Decryption failed. Wrong password? ({e})")
        
        # Determine output file
        if output_file is None:
            if input_path.suffix == '.enc':
                output_path = input_path.with_suffix('')
            else:
                output_path = input_path.with_suffix(input_path.suffix + '.dec')
        else:
            output_path = Path(output_file)
        
        # Write decrypted file
        with open(output_path, 'wb') as outfile:
            outfile.write(plaintext)
        
        print(f"✅ Decrypted: {input_file} -> {output_path}")
        print(f"   Encrypted size: {input_path.stat().st_size:,} bytes")
        print(f"   Decrypted size: {output_path.stat().st_size:,} bytes")
        
        return str(output_path)
    
    def encrypt_batch(self, files: list, password: str, output_dir: str = None):
        """Encrypt multiple files"""
        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            output_file = output_dir / f"{Path(file).name}.enc"
            self.encrypt_file(file, password, output_file)
    
    def decrypt_batch(self, files: list, password: str, output_dir: str = None):
        """Decrypt multiple files"""
        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            input_path = Path(file)
            if input_path.suffix == '.enc':
                output_name = input_path.stem
            else:
                output_name = input_path.name.replace('.enc', '')
            output_file = output_dir / output_name
            self.decrypt_file(file, password, output_file)

def main():
    parser = argparse.ArgumentParser(description="Encrypt or decrypt files using AES-256")
    parser.add_argument('mode', choices=['encrypt', 'decrypt'], help='Operation mode')
    parser.add_argument('files', nargs='+', help='Files to process')
    parser.add_argument('--password', help='Encryption password (prompt if not provided)')
    parser.add_argument('--output-dir', help='Output directory')
    parser.add_argument('--batch', action='store_true', help='Process multiple files')
    
    args = parser.parse_args()
    
    # Get password if not provided
    password = args.password
    if not password:
        import getpass
        password = getpass.getpass("Enter password: ")
        confirm = getpass.getpass("Confirm password: ")
        if args.mode == 'encrypt' and password != confirm:
            print("Error: Passwords don't match", file=sys.stderr)
            sys.exit(1)
    
    encryptor = FileEncryptor()
    
    try:
        if args.mode == 'encrypt':
            if args.batch or len(args.files) > 1:
                encryptor.encrypt_batch(args.files, password, args.output_dir)
            else:
                encryptor.encrypt_file(args.files[0], password, 
                                      Path(args.output_dir) / f"{Path(args.files[0]).name}.enc" 
                                      if args.output_dir else None)
        else:  # decrypt
            if args.batch or len(args.files) > 1:
                encryptor.decrypt_batch(args.files, password, args.output_dir)
            else:
                encryptor.decrypt_file(args.files[0], password, 
                                      Path(args.output_dir) / Path(args.files[0]).stem
                                      if args.output_dir else None)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
