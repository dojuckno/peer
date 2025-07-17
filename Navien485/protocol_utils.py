import re
from functools import reduce
from typing import List, Dict, Optional


class ProtocolUtils:
    """Utilities for RS485 protocol handling."""
    
    @staticmethod
    def xor(hexstring_array: List[str]) -> str:
        """Calculate XOR checksum for hexadecimal string array."""
        return format(
            reduce(lambda x, y: x ^ y, map(lambda x: int(x, 16), hexstring_array)), 
            '02x'
        )

    @staticmethod
    def add(hexstring_array: List[str]) -> str:
        """Calculate ADD checksum for hexadecimal string array."""
        return format(
            reduce(lambda x, y: x + y, map(lambda x: int(x, 16), hexstring_array)), 
            '02x'
        )[-2:]

    @staticmethod
    def is_valid(payload_hexstring: str) -> bool:
        """Validate RS485 payload using checksums."""
        payload_array = [payload_hexstring[i:i+2] for i in range(0, len(payload_hexstring), 2)]
        
        try:
            length_valid = int(payload_array[4], 16) + 7 == len(payload_array)
            xor_valid = ProtocolUtils.xor(payload_array[:-2]) == payload_array[-2:-1][0]
            add_valid = ProtocolUtils.add(payload_array[:-1]) == payload_array[-1:][0]
            
            return length_valid and xor_valid and add_valid
        except (ValueError, IndexError):
            return False

    @staticmethod
    def parse_payload(payload_hexstring: str) -> Optional[Dict[str, str]]:
        """Parse RS485 payload into components."""
        pattern = (
            r'f7(?P<device_id>0e|12|32|33|36)(?P<device_subid>[0-9a-f]{2})'
            r'(?P<message_flag>[0-9a-f]{2})(?:[0-9a-f]{2})'
            r'(?P<data>[0-9a-f]*)(?P<xor>[0-9a-f]{2})(?P<add>[0-9a-f]{2})'
        )
        
        match = re.match(pattern, payload_hexstring)
        return match.groupdict() if match else None