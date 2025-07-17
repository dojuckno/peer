from datetime import datetime
import time
from typing import List, Dict, Any, Optional
import paho.mqtt.client as mqtt

from config_manager import ConfigManager
from device import Device
from protocol_utils import ProtocolUtils
from logger import setup_logger


class Wallpad:
    """Main controller for Navien Wallpad RS485 to MQTT bridge."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self._device_list: List[Device] = []
        self.logger = setup_logger(f"{__name__}.Wallpad")
        self._setup_mqtt_client()
    
    def _setup_mqtt_client(self) -> None:
        """Initialize and configure MQTT client."""
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_message = self._on_raw_message
        self.mqtt_client.on_disconnect = self._on_disconnect
        
        if self.config.mqtt_username or self.config.mqtt_password:
            self.mqtt_client.username_pw_set(
                username=self.config.mqtt_username, 
                password=self.config.mqtt_password
            )
        
        self.mqtt_client.connect(self.config.mqtt_server, self.config.mqtt_port)
        self.logger.info(f"Connected to MQTT broker at {self.config.mqtt_server}:{self.config.mqtt_port}")

    def add_device(
        self,
        device_name: str,
        device_id: str,
        device_subid: str,
        device_class: str,
        child_devices: List[str] = None,
        mqtt_discovery: bool = True,
        optional_info: Dict[str, Any] = None
    ) -> Device:
        """Add a new device to the wallpad."""
        device = Device(
            device_name, device_id, device_subid, device_class,
            child_devices or [], mqtt_discovery, optional_info or {}
        )
        self._device_list.append(device)
        return device

    def get_device(self, **kwargs) -> Device:
        """Find device by name or ID."""
        device_name = kwargs.get('device_name')
        device_id = kwargs.get('device_id')
        device_subid = kwargs.get('device_subid')
        
        for device in self._device_list:
            if device_name:
                if (device.device_name == device_name or 
                    device_name in [child + device.device_name for child in device.child_devices]):
                    return device
            elif device_id and device_subid:
                if device.device_id == device_id and device.device_subid == device_subid:
                    return device
        
        raise ValueError(f"Device not found with criteria: {kwargs}")

    def _get_subscription_topics(self) -> List[str]:
        """Get list of MQTT topics to subscribe to."""
        topics = [f"{self.config.root_topic}/dev/raw"]
        
        for device in self._device_list:
            for child_name in (device.child_devices if device.child_devices else [""]):
                for attr_name in device.get_status_attr_list():
                    topic = f"{self.config.root_topic}/{device.device_class}/{child_name}{device.device_name}/{attr_name}/set"
                    topics.append(topic)
        
        return topics

    def _register_mqtt_discovery(self) -> None:
        """Register devices with Home Assistant via MQTT discovery."""
        for device in self._device_list:
            if device.mqtt_discovery:
                for topic, payload in device.get_mqtt_discovery_payload(
                    self.config.root_topic, 
                    self.config.homeassistant_root_topic
                ):
                    self.mqtt_client.publish(topic, payload, qos=2, retain=True)

    def listen(self) -> None:
        """Start listening for MQTT messages."""
        self._register_mqtt_discovery()
        
        subscription_topics = self._get_subscription_topics()
        for topic in subscription_topics:
            self.logger.debug(f"Subscribing to: {topic}")
        
        self.mqtt_client.subscribe([(topic, 2) for topic in subscription_topics])
        self.mqtt_client.loop_forever()

    def _on_raw_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming MQTT messages."""
        if msg.topic == f"{self.config.root_topic}/dev/raw":
            self._process_raw_message(client, msg)
        else:
            self._process_command_message(client, msg)

    def _process_raw_message(self, client: mqtt.Client, msg: mqtt.MQTTMessage) -> None:
        """Process raw RS485 messages."""
        for payload_raw_bytes in msg.payload.split(b'\xf7')[1:]:
            payload_hexstring = 'f7' + payload_raw_bytes.hex()
            
            try:
                if ProtocolUtils.is_valid(payload_hexstring):
                    payload_dict = ProtocolUtils.parse_payload(payload_hexstring)
                    if payload_dict:
                        self._publish_device_payload(client, payload_dict)
                else:
                    continue
            except Exception as e:
                error_msg = f"Error processing payload {payload_hexstring}: {str(e)}"
                self.logger.error(error_msg)
                client.publish(f"{self.config.root_topic}/dev/error", error_msg, qos=1, retain=True)

    def _process_command_message(self, client: mqtt.Client, msg: mqtt.MQTTMessage) -> None:
        """Process command messages from MQTT."""
        topic_parts = msg.topic.split('/')
        
        try:
            # Special handling for devices
            if (len(topic_parts) >= 5 and topic_parts[4] == "set"):
                device_name = topic_parts[2]
                
                # Heat exchanger special handling
                if device_name == "전열교환기":
                    # percentage 0 -> power OFF
                    if (topic_parts[3] == "percentage" and msg.payload == b'0'):
                        topic_parts[3] = "power"
                        msg.payload = b'OFF'
                    # power ON -> percentage 33% (1단계)
                    elif (topic_parts[3] == "power" and msg.payload == b'ON'):
                        topic_parts[3] = "percentage"
                        msg.payload = b'1'
            device = self.get_device(device_name=topic_parts[2])
            
            if len(device.child_devices) > 0:
                payload = device.get_command_payload(
                    topic_parts[3], 
                    msg.payload.decode(), 
                    child_name=topic_parts[2]
                )
            else:
                payload = device.get_command_payload(
                    topic_parts[3], 
                    msg.payload.decode()
                )
            
            client.publish(f"{self.config.root_topic}/dev/command", payload, qos=2, retain=False)
            
        except (ValueError, IndexError, UnicodeDecodeError) as e:
            error_msg = f"Error processing command {msg.topic}: {str(e)}"
            self.logger.error(error_msg)
            client.publish(f"{self.config.root_topic}/dev/error", error_msg, qos=1, retain=True)

    def _publish_device_payload(self, client: mqtt.Client, payload_dict: Dict[str, str]) -> None:
        """Publish device status to MQTT."""
        try:
            device = self.get_device(
                device_id=payload_dict['device_id'], 
                device_subid=payload_dict['device_subid']
            )
            
            for topic, value in device.parse_payload(payload_dict, self.config.root_topic).items():
                client.publish(topic, value, qos=1, retain=False)
                
        except ValueError as e:
            self.logger.warning(f"Device not found for payload: {payload_dict}")

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int, properties=None, *args, **kwargs) -> None:
        """Handle MQTT disconnection and attempt reconnection."""
        self.logger.warning(f"Disconnected (rc={rc}), attempting to reconnect...")
        try:
            time.sleep(1)
            client.reconnect()
        except Exception as e:
            self.logger.error(f"Reconnect failed: {e}")