import math
import zlib

class PNG:
    '''
    A class to read, process and save PNG image files.
    Loads PNG file then validates signature
    Reads IHDR chunk to extra metadata
    Decompresses IDAT chunks and applies filtering
    Saves processed image in PNG format
    '''

    def __init__(self):
        self.data = b'' # Initialise variable to an empty byte string
        self.info = ''
        self.width = 0
        self.height = 0
        self.bit_depth = 0
        self.color_type = 0
        self.compress = 0
        self.filter = 0
        self.interlace = 0
        self.img = []

    def load_file(self,file_name):
        try:
            with open(file_name, 'rb') as file: # Open file and read bytes
                self.data = file.read()
                self.info = file_name
                
        except FileNotFoundError:
            self.info = 'file not found'

    def valid_png(self):
        return self.data[:8] == b'\x89PNG\r\n\x1a\n' # Extracts first 8 and returns True if matches valid PNG signature

    def read_header(self):
        if self.valid_png() == False:
            raise ValueError('Not a valid PNG file')

        ihdr_chunk = self.data[8:33] # Image header chunk is 25 bytes long and indexes from 8th byte

        if ihdr_chunk[4:8] != b'IHDR': # Encodes ASCII characters into byte values and compares to set index for chunk
            raise ValueError('IHDR chunk was not found')

        self.width = int.from_bytes(ihdr_chunk[8:12], 'big') # Converts bytes to integers using big endian form (from MSB)
        self.height = int.from_bytes(ihdr_chunk[12:16], 'big')
        self.bit_depth = ihdr_chunk[16]
        self.color_type = ihdr_chunk[17]
        self.compress = ihdr_chunk[18]
        self.filter = ihdr_chunk[19]
        self.interlace = ihdr_chunk[20]

    def read_chunks(self):
        if self.valid_png() == False:
            raise ValueError('Not a valid PNG file')

        pointer = 8
        idat_data = b'' # Buffer to store IDAT chunks

        while pointer < len(self.data):
            chunk_length = int.from_bytes(self.data[pointer:pointer + 4], 'big') # First 4 bytes after signature represent chunk length
            chunk_type = self.data[pointer + 4:pointer + 8]
            chunk_data = self.data[pointer + 8:pointer + 8 + chunk_length]
            pointer += 12 + chunk_length # Moves pointer to the next chunk

            if chunk_type == b'IDAT':
                idat_data += chunk_data # IDAT chunk holds compressed image pixel data 

            elif chunk_type == b'IEND':
                break

            else:
                continue # Skips PLTE and all auxillary chunks

            decompressed_data = zlib.decompress(idat_data)
            row_length = self.width*3 + 1 # 3 bytes per pixel (RBG) + 1 filter byte
            rows = [decompressed_data[i:i + row_length] for i in range(0, len(decompressed_data), row_length)]

            if len(rows) != self.height:
                raise ValueError(f'There has been a data mismatch. Expected {self.height} rows, but got {len(rows)} rows')

            previous_row = [0] * (self.width*3) # Empty row for the first filter pass

            for row in rows:
                filter_type = row[0] # First byte is the filter byte
                row_data = list(row[1:]) # Extract pixel data after filter byte
                filtered_row = self.apply_filter(filter_type, row_data, previous_row) # Applied the appropriate filter
                pixels = [list(filtered_row[i:i+3]) for i in range(0, len(filtered_row), 3)] # Extract RGB pixels

                if len(pixels) != self.width:
                    raise ValueError(f'There has been a row mismatch. Expected {self.width} pixels but got {len(pixels)} pixels')

                self.img.append(pixels) # Store processed rows in image list
                previous_row = filtered_row # Updata the previous row

    def apply_filter(self, filter_type, current_row, previous_row):
        if filter_type == 0: # No filter
            return current_row

        elif filter_type == 1: # Sub filter
            for i in range(3,len(current_row)): # First 3 pixels will have no left panel 
                current_row[i] = (current_row[i] + current_row[i-3]) % 256 # Ensures pixel value stays within range of 0-255
                
        elif filter_type == 2: # Up filter
            for i in range(len(current_row)):
                current_row[i] = (current_row[i] + previous_row[i]) % 256

        elif filter_type == 3: # Avergae filter
            for i in range(len(current_row)):
                a = current_row[i-3] if i >= 3 else 0
                b = previous_row[i]
                current_row[i] = (current_row[i] + (a+b) // 2) % 256

        elif filter_type == 4: # Paeth filter
            for i in range(len(current_row)):
                a = current_row[i-3] if i >= 3 else 0
                b = previous_row[i]
                c = previous_row[i -3] if i >= 3 else 0
                current_row[i] = (current_row[i] + self.paeth_predictor(a, b, c)) % 256
        return current_row

    def paeth_predictor(self, a, b, c): # left, above, upper left
        '''
        Computes paeth predictor for a pixel
        Used in PNG filtering to estimate pixel value based on left, above and upper left neighbours
        Selects neighbour closest to pixel value to reduce sum of absolute differences 
        '''
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)

        if pa <= pb and pa <= pc:
            Pr = a
        elif pb <= pc:
            Pr = b           
        else:
            Pr = c
        return Pr

    def save_rgb(self, file_name, rgb_option):
        if rgb_option not in {1, 2, 3}:
            raise ValueError('Invalid rgb_option. Must be 1, 2 or 3')

        # Preallocate the buffer for efficiency
        row_length = self.width*3 + 1
        filtered_data = bytearray(row_length * self.height)
        index = 0 # Tracks current position of filtered data 

        for row in self.img:
            filtered_data[index] = 0 # No filter byte
            index += 1 # Adds filter byte to the start of each row

            for pixel in row:
                if rgb_option == 1: # Red channel
                    filtered_data[index:index + 3] = (pixel[0], 0, 0) # Assign three bytes at a time and set other channels to zero 
                    
                elif rgb_option == 2: # Green channel
                    filtered_data[index:index + 3] = (0, pixel[1], 0)

                elif rgb_option == 3: # Blue channel
                    filtered_data[index:index + 3] = (0, 0, pixel[2])
                index += 3

        # Compress the filtered data
        compressed_data = zlib.compress(filtered_data, level = 3) # Fast compression level

        # Create PNG structure
        png_data = (b'\x89PNG\r\n\x1a\n' +
                    self.create_chunk(b'IHDR',
                                      self.width.to_bytes(4,'big') + # Represents width as 4 byte integers in big endian form
                                      self.height.to_bytes(4,'big') +
                                      bytes([self.bit_depth, self.color_type, self.compress, self.filter, self.interlace])) +
                    self.create_chunk(b'IDAT', compressed_data) +
                    self.create_chunk(b'IEND', b''))

        # Write the file
        with open(file_name, 'wb') as file: # Opens file and writes bytes
            file.write(png_data)

    def create_chunk(self, chunk_type, chunk_data):
        '''
        Helper method to create PNG chunks
        Adds length and CRC to each chunk
        '''

        length = len(chunk_data).to_bytes(4,'big')
        crc = zlib.crc32(chunk_type + chunk_data).to_bytes(4,'big')
        return length + chunk_type + chunk_data + crc
                    
                    
                    
        
            
        
            
                
            
                
            
                
            
    
                    
            
