"""
RouterOS API binary protocol implementation.
Compatible with RouterOS 6.x and 7.x (same protocol).

Wire format:
  Sentence = Word* + ZeroWord
  Word     = Length + Data
  ZeroWord = 0x00
  Length   = variable (1–5 bytes)

Response types:
  !re    = data reply
  !done  = command completed
  !trap  = error
  !fatal = fatal error (connection will close)
"""

import struct
import hashlib


# ─── Length Encoding ──────────────────────────────────────────────────────────

def encode_length(length: int) -> bytes:
    if length < 0x80:
        return struct.pack("B", length)
    elif length < 0x4000:
        return struct.pack(">H", length | 0x8000)
    elif length < 0x200000:
        b = struct.pack(">I", length | 0xC00000)
        return b[1:]  # 3 bytes
    elif length < 0x10000000:
        return struct.pack(">I", length | 0xE0000000)
    else:
        return b"\xF0" + struct.pack(">I", length)


def decode_length(data: bytes, offset: int) -> tuple[int, int]:
    """Returns (length, new_offset)."""
    b = data[offset]
    if b < 0x80:
        return b, offset + 1
    elif b < 0xC0:
        val = struct.unpack(">H", data[offset:offset + 2])[0] & 0x3FFF
        return val, offset + 2
    elif b < 0xE0:
        # 3 bytes – pad to 4
        raw = b"\x00" + data[offset:offset + 3]
        val = struct.unpack(">I", raw)[0] & 0x1FFFFF
        return val, offset + 3
    elif b < 0xF0:
        val = struct.unpack(">I", data[offset:offset + 4])[0] & 0x0FFFFFFF
        return val, offset + 4
    else:
        val = struct.unpack(">I", data[offset + 1:offset + 5])[0]
        return val, offset + 5


# ─── Word / Sentence Encoding ─────────────────────────────────────────────────

def encode_word(word: str) -> bytes:
    data = word.encode("utf-8")
    return encode_length(len(data)) + data


def build_sentence(words: list[str]) -> bytes:
    return b"".join(encode_word(w) for w in words) + b"\x00"


# ─── Sentence Decoding ────────────────────────────────────────────────────────

def decode_sentence(data: bytes, offset: int = 0) -> tuple[list[str], int]:
    """
    Decode one sentence from a byte buffer.
    Returns (words, new_offset). words is empty list if no data yet.
    """
    words = []
    while offset < len(data):
        if offset >= len(data):
            break
        length, offset = decode_length(data, offset)
        if length == 0:
            break  # end of sentence
        if offset + length > len(data):
            # incomplete – caller must buffer
            raise BufferError("Incomplete sentence data")
        word = data[offset:offset + length].decode("utf-8", errors="replace")
        words.append(word)
        offset += length
    return words, offset


def parse_response(words: list[str]) -> dict:
    """
    Parse RouterOS API response words into a structured dict.

    Returns:
        {
            "type":  "!re" | "!done" | "!trap" | "!fatal",
            "tag":   int | None,
            "attrs": {key: value, ...},
        }
    """
    result = {"type": None, "tag": None, "attrs": {}}
    for word in words:
        if word.startswith("!"):
            result["type"] = word
        elif word.startswith(".tag="):
            try:
                result["tag"] = int(word[5:])
            except ValueError:
                result["tag"] = word[5:]
        elif word.startswith("="):
            # =key=value
            eq2 = word.index("=", 1)
            key = word[1:eq2]
            value = word[eq2 + 1:]
            result["attrs"][key] = value
        elif word.startswith("?"):
            # query word – store as-is
            result["attrs"][word] = True
    return result


# ─── MD5 Login Helper (ROS6 and ROS7 fallback) ───────────────────────────────

def md5_challenge_response(password: str, challenge_hex: str) -> str:
    """
    RouterOS MD5 login:
      MD5( 0x00 + password_bytes + challenge_bytes )
    Returns lowercase hex string.
    """
    challenge_bytes = bytes.fromhex(challenge_hex)
    h = hashlib.md5()
    h.update(b"\x00")
    h.update(password.encode("utf-8"))
    h.update(challenge_bytes)
    return h.hexdigest()
