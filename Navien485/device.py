import re
import json
from typing import Dict, List, Any, Callable, Optional, Tuple
from collections import defaultdict
from json import dumps as json_dumps


class Device:
    """Represents a smart home device connected via RS485."""
    
    def __init__(
        self,
        device_name: str,
        device_id: str,
        device_subid: str,
        device_class: str,
        child_devices: List[str] = None,
        mqtt_discovery: bool = True,
        optional_info: Dict[str, Any] = None
    ):
        self.device_name = device_name
        self.device_id = device_id
        self.device_subid = device_subid
        self.device_unique_id = f'rs485_{self.device_id}_{self.device_subid}'
        self.device_class = device_class
        self.child_devices = child_devices or []
        self.mqtt_discovery = mqtt_discovery
        self.optional_info = optional_info or {}
        
        self.status_messages: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.command_messages: Dict[str, Dict[str, Any]] = {}

    def register_status(
        self,
        message_flag: str,
        attr_name: str,
        regex: str,
        topic_class: str,
        device_name: Optional[str] = None,
        process_func: Callable[[str], Any] = lambda v: v
    ) -> None:
        """Register a status message handler for this device."""
        device_name = device_name or self.device_name
        self.status_messages[message_flag].append({
            'regex': regex,
            'process_func': process_func,
            'device_name': device_name,
            'attr_name': attr_name,
            'topic_class': topic_class
        })

    def register_command(
        self,
        message_flag: str,
        attr_name: str,
        topic_class: str,
        controll_id: Optional[List[str]] = None,
        process_func: Callable[[str], str] = lambda v: v
    ) -> None:
        """Register a command message handler for this device."""
        self.command_messages[attr_name] = {
            'message_flag': message_flag,
            'attr_name': attr_name,
            'topic_class': topic_class,
            'process_func': process_func,
            'controll_id': controll_id
        }

    def parse_payload(self, payload_dict: Dict[str, str], root_topic: str) -> Dict[str, Any]:
        """Parse incoming payload and return topic-value pairs."""
        result = {}
        
        for status in self.status_messages[payload_dict['message_flag']]:
            parse_status = re.match(status['regex'], payload_dict['data'])
            
            if not parse_status:
                continue
                
            if len(self.child_devices) > 0:
                for index, child_device in enumerate(self.child_devices):
                    topic = f"{root_topic}/{self.device_class}/{child_device}{self.device_name}/{status['attr_name']}"
                    
                    # Special handling for climate power and away_mode with bit operations
                    if (status['attr_name'] in ["power", "away_mode"] and 
                        self.device_class == "climate"):
                        # 원본과 동일: 비트 연산 결과를 정수로 process_func에 전달
                        result[topic] = status['process_func'](
                            int(parse_status.group(1), 16) & (1 << index)
                        )
                    else:
                        result[topic] = status['process_func'](parse_status.group(index + 1))
            else:
                topic = f"{root_topic}/{self.device_class}/{self.device_name}/{status['attr_name']}"
                result[topic] = status['process_func'](parse_status.group(1))
                
        return result

    def get_command_payload(
        self,
        attr_name: str,
        attr_value: str,
        child_name: Optional[str] = None
    ) -> bytes:
        """Generate command payload for this device."""
        from protocol_utils import ProtocolUtils
        
        attr_value = self.command_messages[attr_name]['process_func'](attr_value)
        
        if child_name is not None:
            idx = [child + self.device_name for child in self.child_devices].index(child_name)
            command_payload = [
                'f7', self.device_id, self.command_messages[attr_name]['controll_id'][idx],
                self.command_messages[attr_name]['message_flag'], '01', attr_value
            ]
        # Special handling for elevator
        elif self.device_id == '33' and self.command_messages[attr_name]['message_flag'] == '81':
            command_payload = [
                'f7', self.device_id, self.device_subid,
                self.command_messages[attr_name]['message_flag'], '03', '00', attr_value, '00'
            ]
        else:
            # 환풍기 percentage 명령은 특별한 형식 사용
            if (self.device_id == '32' and 
                self.command_messages[attr_name]['message_flag'] == '42'):
                command_payload = [
                    'f7', self.device_id, self.device_subid,
                    self.command_messages[attr_name]['message_flag'], '01', attr_value
                ]
            else:
                command_payload = [
                    'f7', self.device_id, self.device_subid,
                    self.command_messages[attr_name]['message_flag'], '00'
                ]
        
        command_payload.append(ProtocolUtils.xor(command_payload))
        command_payload.append(ProtocolUtils.add(command_payload))
        
        return bytes(bytearray.fromhex(' '.join(command_payload)))

    def get_mqtt_discovery_payload(
        self,
        root_topic: str,
        homeassistant_root_topic: str
    ) -> List[Tuple[str, str]]:
        """Generate MQTT discovery payloads for Home Assistant."""
        discovery_list = []
        
        if len(self.child_devices) > 0:
            for idx, child in enumerate(self.child_devices):
                unique_id_join = self.device_unique_id + str(idx)
                device_name_join = child + self.device_name
                
                topic = f"{homeassistant_root_topic}/{self.device_class}/{unique_id_join}/config"
                result = {
                    '~': f"{root_topic}/{self.device_class}/{device_name_join}",
                    'name': device_name_join,
                    'uniq_id': unique_id_join,
                    'device_class': self.device_class,
                }
                result.update(self.optional_info)
                
                for status_list in self.status_messages.values():
                    for status in status_list:
                        result[status['topic_class']] = f"~/{status['attr_name']}"

                for status_list in self.command_messages.values():
                    result[status_list['topic_class']] = f"~/{status_list['attr_name']}/set"

                result['device'] = {
                    'identifiers': unique_id_join,
                    'name': device_name_join
                }
                discovery_list.append((topic, json_dumps(result, ensure_ascii=False)))
        else:
            topic = f"{homeassistant_root_topic}/{self.device_class}/{self.device_unique_id}/config"
            result = {
                '~': f"{root_topic}/{self.device_class}/{self.device_name}",
                'name': self.device_name,
                'uniq_id': self.device_unique_id,
            }
            result.update(self.optional_info)
            
            for status_list in self.status_messages.values():
                for status in status_list:
                    result[status['topic_class']] = f"~/{status['attr_name']}"

            for status_list in self.command_messages.values():
                result[status_list['topic_class']] = f"~/{status_list['attr_name']}/set"

            result['device'] = {
                'identifiers': self.device_unique_id,
                'name': self.device_name
            }
            discovery_list.append((topic, json_dumps(result, ensure_ascii=False)))
            
        return discovery_list
    
    def get_status_attr_list(self) -> List[str]:
        """Get list of all status attribute names for this device."""
        return list(set(
            status['attr_name'] 
            for status_list in self.status_messages.values() 
            for status in status_list
        ))