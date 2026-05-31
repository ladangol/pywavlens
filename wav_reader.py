
# Ladan Golshanara, September 2025

import os
import struct
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
    audio_format = 0

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
        chunk_id_bytes = f.read(4)
        if len(chunk_id_bytes) < 4:
            break
        chunk_size_bytes = f.read(4)
        if len(chunk_size_bytes) < 4:
            break
        chunk_id = chunk_id_bytes.decode("ascii")
        chunk_size = int.from_bytes(chunk_size_bytes,"little")
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
            audio_format = fmt_code
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

            if fmt_code == 0xFFFE and chunk_size - bytes_read >= 24:
                extension_size = int.from_bytes(f.read(2),"little")
                valid_bits_per_sample = int.from_bytes(f.read(2),"little")
                channel_mask = int.from_bytes(f.read(4),"little")
                subformat = f.read(16)
                subformat_code = int.from_bytes(subformat[0:4],"little")
                audio_format = subformat_code
                bytes_read += 24
                print(" - extension size: ", extension_size)
                print(" - valid bits_per_sample: ", valid_bits_per_sample)
                print(" - channel mask: ", channel_mask)
                print(" - subformat code: ", subformat_code)

            ## We read what we wanted from the fmt tag, 
            ## skip the rest 

            f.seek(chunk_size-bytes_read,1)
            print("bytes remaining in fmt chunk: ",chunk_size-bytes_read)

            continue

        elif (chunk_id.startswith("data")):
            if fmt_found == False:
                print("error: no fmt chunk, don't know how to interpret the data")
                break
            data_start = f.tell()
            if audio_format not in (0x0001, 0x0003):
                print("error: unsupported fmt code: ", fmt_code)
                f.seek(data_start + chunk_size)
                continue
            if bits_per_sample % 8 != 0:
                print("error: unsupported bits_per_sample: ", bits_per_sample)
                f.seek(data_start + chunk_size)
                continue
            if audio_format == 0x0001 and bits_per_sample not in (8, 16, 24, 32):
                print("error: unsupported PCM bits_per_sample: ", bits_per_sample)
                f.seek(data_start + chunk_size)
                continue
            if audio_format == 0x0003 and bits_per_sample != 32:
                print("error: unsupported IEEE float bits_per_sample: ", bits_per_sample)
                f.seek(data_start + chunk_size)
                continue
            bytes_to_read = int(bits_per_sample/8)
            bytes_per_frame = bytes_to_read * num_channels
            num_sample_frames = chunk_size // bytes_per_frame
            samples_to_show_at_start = 5
            samples_to_show_at_end = 2

            print(" - sample frames: ", num_sample_frames)

            def print_sample_frame(sample_index):
                print("sample ", sample_index)
                for chan in range(num_channels):
                    float_sample = 0.0
                    ## Read the appropriate number of bytes for a sample, convert to float
                    sample_bytes = f.read(bytes_to_read)
                    if audio_format == 0x0003 and bits_per_sample == 32:  #for IEEE wav
                        float_sample = struct.unpack("<f", sample_bytes)[0]
                    elif bits_per_sample == 8:
                        ## 8-bit PCM WAV samples are unsigned, centered around 128
                        int_sample = int.from_bytes(sample_bytes,"little",signed=False)
                        float_sample = (int_sample - 128) / 128.0
                    else:
                        int_sample = int.from_bytes(sample_bytes,"little",signed=True)
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

            samples_at_start = min(samples_to_show_at_start, num_sample_frames)
            for i in range(samples_at_start):
                print_sample_frame(i)

            if num_sample_frames > samples_to_show_at_start + samples_to_show_at_end:
                print("...")
                bytes_to_skip = (num_sample_frames - samples_to_show_at_start - samples_to_show_at_end) * bytes_per_frame
                f.seek(bytes_to_skip, 1)
                for i in range(num_sample_frames - samples_to_show_at_end, num_sample_frames):
                    print_sample_frame(i)
            else:
                for i in range(samples_at_start, num_sample_frames):
                    print_sample_frame(i)

            f.seek(data_start + chunk_size)
            continue
                
        ## If EOF, break out of the loop
        if (f.tell() == os.fstat(f.fileno()).st_size):
            break

        ## Otherwise, skip chunk
        f.seek(chunk_size,1)
        
    
finally:
    ## Close the file
    f.close()
