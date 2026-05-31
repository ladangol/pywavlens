# Example code by Waveshaper AI
# Ladan Golshanara, September 2022

import os
import sys

## Filename is the first argument
filename = sys.argv[1]

## Create a file handle 
f = open(filename,"rb")

try:

    ## Located fmt chunk
    fmt_found = False

    num_channels = 0
    bits_per_sample = 0

    ## Get the original filename
    orig_file_size = os.path.getsize(filename)
    print("Total file size on filesystem: ",orig_file_size)

    ## Read the first 4 bytes of the file
    riff_id = f.read(4)
    print("First 4 bytes should be the RIFF tag: ",riff_id)

    ## Read the next 4 bytes of the file 
    size_bytes = f.read(4)
    print("Next 4 bytes is size of total sub chunks (total file size minus 8 header bytes): ", int.from_bytes(size_bytes, "little"))

    ## Read the next 4 bytes of the file
    wav_id = f.read(4)
    print("Next 4 bytes should be the WAVE tag: ",wav_id)
    
    ## Now we may have an arbitrary number of chunks, need to loop to find the two we care about: fmt and data
    while(True):

        ## Read chunk header 
        chunk_id = f.read(4).decode("ascii")
        chunk_size = int.from_bytes(f.read(4),"little")
        print("Chunk tag: ",chunk_id)
        print("Chunk size: ",chunk_size)

        ## Do fmt chunk
        if chunk_id.startswith("fmt"):
            ## Set the flag to true, we have encountered the fmt chunk
            fmt_found = True

            ## Because we might stop reading the chunk before it is done,
            ## track the number of bytes of the chunk we have read
            ## so we can skip the rest, if there is more than the fields we
            ## extract
            bytes_read = 0

            ## Read the fmt code (PCM = 1)
            fmt_code = int.from_bytes(f.read(2),"little")
            print(" - fmt code: ",fmt_code)
            bytes_read += 2

            ## Read the number of channels
            num_channels = int.from_bytes(f.read(2),"little")
            print(" - channels: ",num_channels)
            bytes_read += 2

            ## Read the sample rate
            sample_rate = int.from_bytes(f.read(4),"little")
            print(" - samples per second: ",sample_rate)
            bytes_read += 4

            ## Read the byte rate
            byte_rate = int.from_bytes(f.read(4),"little")
            print(" - byte rate: ", byte_rate)
            bytes_read += 4

            block_align = int.from_bytes(f.read(2),"little")
            print(" - block align: ", block_align)
            bytes_read += 2
            
            bits_per_sample = int.from_bytes(f.read(2),"little")
            print(" - bits_per_sample: ", bits_per_sample)
            bytes_read += 2

            ## We read what we wanted from the fmt tag, 
            ## skip the rest 

            f.seek(chunk_size-bytes_read,1)
            print("bytes remaining in fmt chunk: ",chunk_size-bytes_read)

            continue

        elif (chunk_id.startswith("data")):
            bytes_read = 0
            if fmt_found == False:
                print("error: no fmt chunk, don't know how to interpret the data")
                break
            bytes_to_read = int(bits_per_sample/8)

	    # Note that the number of samples here is hard coded..
            for i in range(10000):
                print("num_channels: ",num_channels)
                for chan in range(num_channels):
                    float_sample = 0.0
                    ## Read the appropriate number of bytes for a sample, convert to float
                    int_sample = int.from_bytes(f.read(bytes_to_read),"little",signed=True)
                    if bits_per_sample == 16:
                        ## Normalize to [-1,1) for 16-bits
                        float_sample = int_sample / 32768.0
                    elif bits_per_sample == 24:
                        ## Normalize to [-1,1) for 24-bits
                        float_sample = int_sample / 0x800000
                    elif bits_per_sample == 32:
                        ## Normalize to [-1,1) for 32-bits
                        float_sample = int_sample / 0x7fffffff
                    print("chan ",chan, ": ",float_sample)
                    bytes_read += bytes_to_read

            f.seek(chunk_size-bytes_read,1)
            continue
                
        ## If EOF, break out of the loop
        if (f.tell() == os.fstat(f.fileno()).st_size):
            break

        ## Otherwise, skip chunk
        f.seek(chunk_size,1)
        
    
finally:
    ## Close the file
    f.close()