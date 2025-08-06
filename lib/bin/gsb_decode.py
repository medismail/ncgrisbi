#from Crypto.Cipher import DES
from Cryptodome.Cipher import DES
from getpass import getpass
import struct

V2_MARKER = b"Grisbi encryption v2: "
V2_MARKER_SIZE = len(V2_MARKER)

password = None

def align_to_8_bytes(length):
    return (length + 7) & (~7)

def des_string_to_key(password):
    # Initialize the key to 8 bytes of zero
    key = [0] * 8
    password = password.encode('utf-8')
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

def bitwise_xor_bytes(a, b):
    result_int = int.from_bytes(a, byteorder="big") ^ int.from_bytes(b, byteorder="big")
    return result_int.to_bytes(max(len(a), len(b)), byteorder="big")

def apply_des_checksum(password, key):
    # Create a DES key schedule
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
    # Ensure each byte has odd parity using the odd_parity array
    key = bytearray(key)
    for i in range(len(key)):
        key[i] = odd_parity[key[i]]
    return bytes(key)

def encrypt_v2(password, file_content_str):
    # Ensure the password is 8 bytes long
    key_bytes = des_string_to_key(password)
    iv = set_odd_parity(key_bytes)

    # Create a DES key and key schedule
    key = DES.new(key_bytes, DES.MODE_CBC, iv)

    # Create a temporary buffer that will hold data to be encrypted
    file_content = file_content_str.encode("utf-8")
    to_encrypt_length = V2_MARKER_SIZE + len(file_content)
    to_encrypt_content = V2_MARKER + file_content

    # Allocate the output file and copy the special marker at its beginning
    output_length = V2_MARKER_SIZE + align_to_8_bytes(to_encrypt_length)
    output_content = V2_MARKER + b'\x00' * (output_length - V2_MARKER_SIZE)

    # Encrypt the data and put it in the right place in the output buffer
    encrypted_content = key.encrypt(to_encrypt_content.ljust(output_length - V2_MARKER_SIZE, b'\x00'))
    output_content = V2_MARKER + encrypted_content

    return output_content

def decrypt_v2(password, file_content):
    # Ensure the password is 8 bytes long
    key_bytes = des_string_to_key(password)
    iv = set_odd_parity(key_bytes)

    # Create a DES key and key schedule
    key = DES.new(key_bytes, DES.MODE_CBC, iv)

    # Create a temporary buffer that will hold the decrypted data without the first marker
    decrypted_len = len(file_content) - V2_MARKER_SIZE
    decrypted_buf = key.decrypt(file_content[V2_MARKER_SIZE:])

    # If the password was correct, the second marker should appear in the first few bytes of the decrypted content
    if decrypted_buf[:V2_MARKER_SIZE] != V2_MARKER:
        #raise ValueError("Incorrect password or corrupted file")
        print('{"Error": "Incorrect password or corrupted file"}')
        exit()

    # Copy the decrypted data to a final buffer, leaving out the second marker
    output_buf = decrypted_buf[V2_MARKER_SIZE:].rstrip(b'\x00')

    return output_buf

def check_encrypt_gsb(file_content):
    return file_content[:V2_MARKER_SIZE] == V2_MARKER

def read_gsb_file(file_path):
    global password
    with open(file_path, 'rb') as f:
        file_content = f.read()
    if file_content[:V2_MARKER_SIZE] != V2_MARKER:
        return file_content
    else:
        password = getpass()
        return decrypt_v2(password, file_content)

def write_gsb_file(file_path, file_content):
    if (password):
        with open(file_path, 'wb') as f:
            f.write(encrypt_v2(password, file_content))
    else:
        with open(file_path, 'w') as f:
            f.write(file_content)

##def main():
#    password = ""  # Update this with your password
#
#    file_path = "example.gsb"  # Update this path to your Grisbi file
#
#    # Read the file content
#    file_content = read_gsb_file(file_path)
#
#    # Encrypt the file content
#    encrypted_content = encrypt_v2(password, file_content)
#    print("Encryption successful!")
#
#    # Write the encrypted content to a new file
#    encrypted_file_path = "encrypted_example.gsb"
#    write_gsb_file(encrypted_file_path, encrypted_content)
#    print(f"Encrypted content written to {encrypted_file_path}")
#
#    encrypted_file_path = "test.gsb"  # Update this path to your Grisbi file
#
#    # Read the encrypted file content
#    encrypted_content = read_gsb_file(encrypted_file_path)
#
#    # Decrypt the file content
#    try:
#        decrypted_content = decrypt_v2(password, encrypted_content)
#        print("Decryption successful!")
#
#        # Write the decrypted content to a new file
#        decrypted_file_path = "decrypted_example.gsb"
#        write_gsb_file(decrypted_file_path, decrypted_content)
#        print(f"Decrypted content written to {decrypted_file_path}")
#
#    except ValueError as e:
#        print(f"Error: {e}")
#
#if __name__ == "__main__":
#    main()
