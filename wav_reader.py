# Ladan Golshanara, September 2025

import argparse
import os
import struct


WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE


def format_name(format_code):
    names = {
        WAVE_FORMAT_PCM: "PCM",
        WAVE_FORMAT_IEEE_FLOAT: "IEEE Float",
        WAVE_FORMAT_EXTENSIBLE: "Extensible",
        0x0011: "IMA ADPCM",
        0x0055: "MPEG Layer 3",
    }
    return names.get(format_code, "Unknown")


def channel_description(num_channels):
    if num_channels == 1:
        return "Mono"
    if num_channels == 2:
        return "Stereo"
    return str(num_channels) + " channels"


def sample_type(audio_format, bits_per_sample):
    if audio_format == WAVE_FORMAT_IEEE_FLOAT:
        return "float32"
    return "int" + str(bits_per_sample)


def channel_label(channel, num_channels):
    if num_channels == 1:
        return "Mono"
    if num_channels == 2:
        return ["Left", "Right"][channel]
    return "Channel " + str(channel)


def layout_label(channel, frame_index, num_channels):
    if num_channels == 1:
        return "M" + str(frame_index)
    if num_channels == 2:
        return ["L", "R"][channel] + str(frame_index)
    return "C" + str(channel) + "_" + str(frame_index)


def is_supported(audio_format, bits_per_sample):
    if audio_format == WAVE_FORMAT_PCM and bits_per_sample in (8, 16, 24, 32):
        return True
    if audio_format == WAVE_FORMAT_IEEE_FLOAT and bits_per_sample == 32:
        return True
    return False


def unsupported_reason(fmt_code, audio_format, bits_per_sample):
    if audio_format not in (WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT):
        return format_name(fmt_code) + " is not yet supported."
    if audio_format == WAVE_FORMAT_IEEE_FLOAT:
        return "Only 32-bit IEEE float is supported."
    return "PCM " + str(bits_per_sample) + "-bit samples are not yet supported."


def decode_sample(sample_bytes, audio_format, bits_per_sample):
    if audio_format == WAVE_FORMAT_IEEE_FLOAT:
        return struct.unpack("<f", sample_bytes)[0]

    if bits_per_sample == 8:
        int_sample = int.from_bytes(sample_bytes, "little", signed=False)
        return (int_sample - 128) / 128.0

    int_sample = int.from_bytes(sample_bytes, "little", signed=True)
    if bits_per_sample == 16:
        return int_sample / 32768.0
    if bits_per_sample == 24:
        return int_sample / 0x800000
    if bits_per_sample == 32:
        return int_sample / 0x7fffffff

    raise ValueError("unsupported PCM bits_per_sample: " + str(bits_per_sample))


def read_wav(filename):
    metadata = {
        "filename": filename,
        "filesystem_size": os.path.getsize(filename),
        "chunks": [],
        "fmt": None,
        "data": None,
        "riff_size": None,
        "wave_id": None,
        "is_riff": False,
    }

    with open(filename, "rb") as f:
        riff_id = f.read(4)
        metadata["is_riff"] = riff_id == b"RIFF"
        metadata["riff_size"] = int.from_bytes(f.read(4), "little")
        metadata["wave_id"] = f.read(4).decode("ascii", errors="replace")

        while True:
            chunk_id_bytes = f.read(4)
            if len(chunk_id_bytes) < 4:
                break
            chunk_size_bytes = f.read(4)
            if len(chunk_size_bytes) < 4:
                break

            chunk_id = chunk_id_bytes.decode("ascii", errors="replace")
            chunk_size = int.from_bytes(chunk_size_bytes, "little")
            chunk_start = f.tell()
            metadata["chunks"].append({"id": chunk_id, "size": chunk_size, "start": chunk_start})

            if chunk_id == "fmt ":
                fmt = read_fmt_chunk(f, chunk_size)
                metadata["fmt"] = fmt
            elif chunk_id == "data":
                metadata["data"] = {"size": chunk_size, "start": chunk_start}
                f.seek(chunk_size, 1)
            else:
                f.seek(chunk_size, 1)

            if chunk_size % 2 == 1:
                f.seek(1, 1)

    return metadata


def read_fmt_chunk(f, chunk_size):
    bytes_read = 0
    fmt_code = int.from_bytes(f.read(2), "little")
    num_channels = int.from_bytes(f.read(2), "little")
    sample_rate = int.from_bytes(f.read(4), "little")
    byte_rate = int.from_bytes(f.read(4), "little")
    block_align = int.from_bytes(f.read(2), "little")
    bits_per_sample = int.from_bytes(f.read(2), "little")
    bytes_read += 16

    fmt = {
        "chunk_size": chunk_size,
        "fmt_code": fmt_code,
        "audio_format": fmt_code,
        "num_channels": num_channels,
        "sample_rate": sample_rate,
        "byte_rate": byte_rate,
        "block_align": block_align,
        "bits_per_sample": bits_per_sample,
        "extension_size": None,
        "valid_bits_per_sample": None,
        "channel_mask": None,
        "subformat_code": None,
    }

    if fmt_code == WAVE_FORMAT_EXTENSIBLE and chunk_size - bytes_read >= 24:
        fmt["extension_size"] = int.from_bytes(f.read(2), "little")
        fmt["valid_bits_per_sample"] = int.from_bytes(f.read(2), "little")
        fmt["channel_mask"] = int.from_bytes(f.read(4), "little")
        subformat = f.read(16)
        fmt["subformat_code"] = int.from_bytes(subformat[0:4], "little")
        fmt["audio_format"] = fmt["subformat_code"]
        bytes_read += 24

    f.seek(chunk_size - bytes_read, 1)
    return fmt


def sample_frames_to_show(frame_count):
    samples_to_show_at_start = 5
    samples_to_show_at_end = 2

    if frame_count <= samples_to_show_at_start + samples_to_show_at_end:
        return list(range(frame_count))

    return (
        list(range(samples_to_show_at_start))
        + [None]
        + list(range(frame_count - samples_to_show_at_end, frame_count))
    )


def read_sample_preview(filename, fmt, data):
    if not is_supported(fmt["audio_format"], fmt["bits_per_sample"]):
        return []

    bytes_per_sample = fmt["bits_per_sample"] // 8
    frame_count = data["size"] // fmt["block_align"]
    preview = []

    with open(filename, "rb") as f:
        for frame_index in sample_frames_to_show(frame_count):
            if frame_index is None:
                preview.append(None)
                continue

            f.seek(data["start"] + frame_index * fmt["block_align"])
            channels = []
            for _ in range(fmt["num_channels"]):
                sample_bytes = f.read(bytes_per_sample)
                channels.append(decode_sample(sample_bytes, fmt["audio_format"], fmt["bits_per_sample"]))
            preview.append({"frame": frame_index, "channels": channels})

    return preview


def print_tree(metadata):
    fmt = metadata["fmt"]
    data = metadata["data"]

    if metadata["is_riff"] and metadata["wave_id"] == "WAVE":
        print("✓ RIFF/WAVE file detected")
    else:
        print("✗ Not a RIFF/WAVE file")
    print()

    print("RIFF")
    print("├─ File size: " + str(metadata["filesystem_size"]) + " bytes")
    print("├─ RIFF payload size: " + str(metadata["riff_size"]) + " bytes")
    print("├─ Format: " + str(metadata["wave_id"]))
    print("│")

    if fmt is None:
        print("└─ Status")
        print("   └─ ✗ Missing fmt chunk")
        return

    print("├─ fmt")
    print("│  ├─ Chunk size: " + str(fmt["chunk_size"]) + " bytes")
    print("│  ├─ Format: " + format_name(fmt["fmt_code"]) + " (" + str(fmt["fmt_code"]) + ")")
    if fmt["fmt_code"] == WAVE_FORMAT_EXTENSIBLE:
        print(
            "│  ├─ Subformat: "
            + format_name(fmt["audio_format"])
            + " ("
            + str(fmt["audio_format"])
            + ")"
        )
    print(
        "│  ├─ Channels: "
        + str(fmt["num_channels"])
        + " ("
        + channel_description(fmt["num_channels"])
        + ")"
    )
    print("│  ├─ Sample rate: " + str(fmt["sample_rate"]) + " Hz")
    print("│  ├─ Byte rate: " + str(fmt["byte_rate"]) + " bytes/sec")
    print("│  ├─ Block align: " + str(fmt["block_align"]) + " bytes/frame")
    print("│  └─ Bits per sample: " + str(fmt["bits_per_sample"]))
    print("│")

    if data is None:
        print("└─ Status")
        print("   └─ ✗ Missing data chunk")
        return

    frame_count = data["size"] // fmt["block_align"]
    print("├─ data")
    print("│  ├─ Chunk size: " + str(data["size"]) + " bytes")
    print("│  ├─ Frames: " + str(frame_count))
    print("│  └─ Layout:")
    print("│")
    for frame_index in range(min(3, frame_count)):
        cells = "".join("[" + layout_label(channel, frame_index, fmt["num_channels"]) + "]" for channel in range(fmt["num_channels"]))
        print("│      Frame " + str(frame_index) + ": " + cells)
    if frame_count > 3:
        print("│      ...")
    print("│")

    print_audio_frame_box(fmt)
    print("│")

    if is_supported(fmt["audio_format"], fmt["bits_per_sample"]):
        print("│  Sample values:")
        for sample in read_sample_preview(metadata["filename"], fmt, data):
            if sample is None:
                print("      ...")
                continue
            print("      sample ", sample["frame"])
            for channel, value in enumerate(sample["channels"]):
                print("      chan ", channel, ": ", value)
        print("│")
        print("└─ Status")
        print("   └─ ✓ Supported by this reader")
    else:
        print("└─ Status")
        print("   └─ ✗ " + unsupported_reason(fmt["fmt_code"], fmt["audio_format"], fmt["bits_per_sample"]))
        print("      error: unsupported fmt code: ", fmt["fmt_code"])


def print_audio_frame_box(fmt):
    num_channels = fmt["num_channels"]
    kind = sample_type(fmt["audio_format"], fmt["bits_per_sample"])
    cell_width = max(8, len(kind) + 4)
    top = "│  ┌" + "┬".join("─" * cell_width for _ in range(num_channels)) + "┐"
    middle = "│  │" + "│".join(channel_label(i, num_channels).ljust(cell_width) for i in range(num_channels)) + "│"
    type_line = "│  │" + "│".join(kind.ljust(cell_width) for _ in range(num_channels)) + "│"
    bottom = "│  └" + "┴".join("─" * cell_width for _ in range(num_channels)) + "┘"

    print("│  Audio frame")
    print("│")
    print(top)
    print(middle)
    print(type_line)
    print(bottom)
    print("│")
    print("│  Frame size = " + str(fmt["block_align"]) + " bytes")


def main():
    parser = argparse.ArgumentParser(description="Read and visualize a WAV file.")
    parser.add_argument("filename")
    args = parser.parse_args()

    metadata = read_wav(args.filename)
    print_tree(metadata)


if __name__ == "__main__":
    main()
