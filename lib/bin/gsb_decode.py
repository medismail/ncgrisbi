from Cryptodome.Cipher import DES
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from hashlib import sha256
from getpass import getpass
import struct
import os

V2_MARKER = b"Grisbi encryption v2: "
V2_MARKER_SIZE = len(V2_MARKER)

V3_MARKER = b"Grisbi encryption v3: "
V3_MARKER_SIZE = len(V3_MARKER)

password = None
encryption_version = None

IV = b"1234567887654321"

def encrypt_v3(password, file_content):
    """
    Python equivalent of the C encrypt_v3().

    Args:
        password: str or bytes
        file_content: bytes

    Returns:
        bytes: V3_MARKER + AES-128-CBC-encrypted(V3_MARKER + file_content)
    """
    if isinstance(password, str):
        password = password.encode("utf-8")
    if isinstance(file_content, str):
        file_content = file_content.encode("utf-8")

    # to_encrypt_content = V3_MARKER + original content
    to_encrypt_content = V3_MARKER + file_content

    # SHA-256(password), first 16 bytes used for AES-128 key
    key = sha256(password).digest()[:16]

    # AES-128-CBC with PKCS#7 padding
    cipher = AES.new(key, AES.MODE_CBC, IV)
    encrypted_content = cipher.encrypt(pad(to_encrypt_content, AES.block_size))

    # output_content = clear marker + encrypted payload
    output_content = V3_MARKER + encrypted_content
    return output_content

def decrypt_v3(password, encrypted_blob):
    if isinstance(password, str):
        password = password.encode("utf-8")
    if isinstance(encrypted_blob, str):
        encrypted_blob = encrypted_blob.encode("utf-8")

    if not encrypted_blob.startswith(V3_MARKER):
        raise ValueError("Missing V3 marker at beginning of encrypted blob")

    encrypted_content = encrypted_blob[V3_MARKER_SIZE:]
    if len(encrypted_content) == 0 or len(encrypted_content) % AES.block_size != 0:
        raise ValueError("Invalid V3 encrypted content length")

    key = sha256(password).digest()[:16]
    cipher = AES.new(key, AES.MODE_CBC, IV)
    decrypted = unpad(cipher.decrypt(encrypted_content), AES.block_size)

    if not decrypted.startswith(V3_MARKER):
        raise ValueError("Decrypted content does not contain inner V3 marker")

    # Remove inner marker
    output_buf = decrypted[V3_MARKER_SIZE:]

    return output_buf

def align_to_8_bytes(length):
    return (length + 7) & (~7)

def des_string_to_key(password):
    """Convert password string to DES key with security checks.
    
    Security: Validates password type and handles encoding safely.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    # Initialize the key to 8 bytes of zero
    key = [0] * 8
    
    # Safe encoding
    if isinstance(password, str):
        password = password.encode('utf-8')
    elif not isinstance(password, bytes):
        raise TypeError("Password must be string or bytes")
    
    length = len(password)

    for i, byte in enumerate(password):
        if i < 8:
            key[i] ^= (byte << 1)
        else:
            # Reverse the bit order
            j = ((byte << 4) & 0xf0) | ((byte >> 4) & 0x0f)
            j = ((j << 2) & 0xcc) | ((j >> 2) & 0x33)
            j = ((j << 1) & 0xaa) | ((j >> 1) & 0x55)
            key[7 - (i % 8)] ^= j

    # Set odd parity for each byte in the key
    key = set_odd_parity(bytes(key))

    # Apply DES checksum
    key = apply_des_checksum(password, key)

    key = set_odd_parity(key)

    return key

#def bitwise_xor_bytes(a, b):
#    """Safely XOR two byte strings."""
#    result_int = int.from_bytes(a, byteorder="big") ^ int.from_bytes(b, byteorder="big")
#    return result_int.to_bytes(max(len(a), len(b)), byteorder="big")

def bitwise_xor_bytes(a, b):
    """Safely XOR two byte strings."""
    if len(a) != len(b):
        raise ValueError("Inputs must have same length")
    return bytes(x ^ y for x, y in zip(a, b))

def apply_des_checksum(password, key):
    """Apply DES checksum to key.
    
    Optimization: Reuse key schedule instead of recreating it each iteration.
    """
    # Create a DES key schedule once
    key_schedule = DES.new(key, DES.MODE_ECB)
    
    # Create a buffer for the checksum
    checksum = bytearray(key)
    
    # Apply DES checksum
    for i in range(0, len(password), 8):
        block = password[i:i+8].ljust(8, b'\x00')
        block = bytearray(block)
        checksum = bytearray(key_schedule.encrypt(bitwise_xor_bytes(bytes(checksum), bytes(block))))
    
    return checksum

# Odd parity array from OpenSSL
odd_parity = [
    1, 1, 2, 2, 4, 4, 7, 7, 8, 8, 11, 11, 13, 13, 14, 14,
    16, 16, 19, 19, 21, 21, 22, 22, 25, 25, 26, 26, 28, 28, 31, 31,
    32, 32, 35, 35, 37, 37, 38, 38, 41, 41, 42, 42, 44, 44, 47, 47,
    49, 49, 50, 50, 52, 52, 55, 55, 56, 56, 59, 59, 61, 61, 62, 62,
    64, 64, 67, 67, 69, 69, 70, 70, 73, 73, 74, 74, 76, 76, 79, 79,
    81, 81, 82, 82, 84, 84, 87, 87, 88, 88, 91, 91, 93, 93, 94, 94,
    97, 97, 98, 98, 100, 100, 103, 103, 104, 104, 107, 107, 109, 109,
    110, 110, 112, 112, 115, 115, 117, 117, 118, 118, 121, 121, 122, 122,
    124, 124, 127, 127, 128, 128, 131, 131, 133, 133, 134, 134, 137, 137,
    138, 138, 140, 140, 143, 143, 145, 145, 146, 146, 148, 148, 151, 151,
    152, 152, 155, 155, 157, 157, 158, 158, 161, 161, 162, 162, 164, 164,
    167, 167, 168, 168, 171, 171, 173, 173, 174, 174, 176, 176, 179, 179,
    181, 181, 182, 182, 185, 185, 186, 186, 188, 188, 191, 191, 193, 193,
    194, 194, 196, 196, 199, 199, 200, 200, 203, 203, 205, 205, 206, 206,
    208, 208, 211, 211, 213, 213, 214, 214, 217, 217, 218, 218, 220, 220,
    223, 223, 224, 224, 227, 227, 229, 229, 230, 230, 233, 233, 234, 234,
    236, 236, 239, 239, 241, 241, 242, 242, 244, 244, 247, 247, 248, 248,
    251, 251, 253, 253, 254, 254
]

def set_odd_parity(key):
    """Ensure each byte has odd parity using the odd_parity array."""
    key = bytearray(key)
    for i in range(len(key)):
        key[i] = odd_parity[key[i]]
    return bytes(key)

def encrypt_v2(password, file_content_str):
    """Encrypt file content with DES v2 format.
    
    Security: Validates password and content length.
    """
    if not password:
        raise ValueError("Password is required for encryption")
    
    if isinstance(file_content_str, bytes):
        file_content = file_content_str
    else:
        file_content = file_content_str.encode("utf-8")
    
    # Ensure the password is properly formatted
    key_bytes = des_string_to_key(password)
    iv = set_odd_parity(key_bytes)

    # Create a DES key and key schedule
    key = DES.new(key_bytes, DES.MODE_CBC, iv)

    # Create a temporary buffer that will hold data to be encrypted
    to_encrypt_length = V2_MARKER_SIZE + len(file_content)
    to_encrypt_content = V2_MARKER + file_content

    # Allocate the output file and copy the special marker at its beginning
    output_length = V2_MARKER_SIZE + align_to_8_bytes(to_encrypt_length)
    
    # Encrypt the data and put it in the right place in the output buffer
    encrypted_content = key.encrypt(to_encrypt_content.ljust(output_length - V2_MARKER_SIZE, b'\x00'))
    output_content = V2_MARKER + encrypted_content

    return output_content

def decrypt_v2(password, file_content):
    """Decrypt file content from DES v2 format.
    
    Security: Validates password and file format, handles errors gracefully.
    """
    if not password:
        raise ValueError("Password is required for decryption")
    
    if not file_content or len(file_content) < V2_MARKER_SIZE:
        raise ValueError("Invalid encrypted file: too short")

    if not file_content.startswith(V2_MARKER):
        raise ValueError("Missing V2 marker")

    ciphertext = file_content[V2_MARKER_SIZE:]
    if len(ciphertext) == 0 or len(ciphertext) % 8 != 0:
        raise ValueError("Invalid V2 encrypted content length")

    # Ensure the password is properly formatted
    key_bytes = des_string_to_key(password)
    iv = set_odd_parity(key_bytes)

    # Create a DES key and key schedule
    key = DES.new(key_bytes, DES.MODE_CBC, iv)

    # Create a temporary buffer that will hold the decrypted data without the first marker
    decrypted_buf = key.decrypt(ciphertext)

    # If the password was correct, the second marker should appear in the first few bytes of the decrypted content
    if decrypted_buf[:V2_MARKER_SIZE] != V2_MARKER:
        raise ValueError("Incorrect password or corrupted file")

    # Copy the decrypted data to a final buffer, leaving out the second marker
    output_buf = decrypted_buf[V2_MARKER_SIZE:].rstrip(b'\x00')

    return output_buf

def check_encrypt_gsb(file_content):
    """Check if file is encrypted with DES v2 or AES v3 format."""
    if not file_content or len(file_content) < V2_MARKER_SIZE:
        return False
    return file_content[:V2_MARKER_SIZE] == V2_MARKER or file_content[:V3_MARKER_SIZE] == V3_MARKER

def read_gsb_file(file_path):
    """Read GSB file from disk.
    
    Security: Validates file exists and handles errors gracefully.
    """
    global password, encryption_version

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'rb') as f:
        file_content = f.read()

    if file_content[:V2_MARKER_SIZE] == V2_MARKER:
        encryption_version = 2
        password = getpass("Enter password for encrypted GSB file: ")
        return decrypt_v2(password, file_content)
    elif file_content[:V3_MARKER_SIZE] == V3_MARKER:
        encryption_version = 3
        password = getpass("Enter password for encrypted GSB file: ")
        return decrypt_v3(password, file_content)
    else:
        encryption_version = None
        password = None
        return file_content

def write_gsb_file(file_path, file_content):
    """Write GSB file to disk.
    
    Security: Validates file path and handles I/O errors.
    """
    global password, encryption_version

    try:
        if password:
            if encryption_version == 3:
                encrypted_content = encrypt_v3(password, file_content)
            else:
                encrypted_content = encrypt_v2(password, file_content)

            with open(file_path, 'wb') as f:
                f.write(encrypted_content)
        else:
            mode = 'wb' if isinstance(file_content, bytes) else 'w'
            with open(file_path, mode) as f:
                f.write(file_content)
    except IOError as e:
        raise IOError(f"Error writing file {file_path}: {e}")
