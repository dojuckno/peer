import json
from typing import Dict, Any, Optional
from logger import setup_logger


class ConfigManager:
    """Configuration management for Navien RS485 MQTT bridge."""
    
    def __init__(self, config_path: str = "/data/options.json"):
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.logger = setup_logger(f"{__name__}.ConfigManager")
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            
            # 설정 형식 확인 및 로깅
            if "options" in self._config:
                self.logger.info(f"Home Assistant 애드온 형식 설정 로드: {self.config_path}")
            else:
                self.logger.info(f"직접 설정 형식 로드: {self.config_path}")
                
        except FileNotFoundError:
            self.logger.error(f"설정 파일({self.config_path})을 찾을 수 없습니다.")
            self._config = {}
        except json.JSONDecodeError:
            self.logger.error(f"설정 파일({self.config_path})의 JSON 형식이 올바르지 않습니다.")
            self._config = {}
    
    @property
    def mqtt_config(self) -> Dict[str, Any]:
        """Get MQTT configuration."""
        # Home Assistant 애드온 형식인 경우 options 내부에서 찾기
        if "options" in self._config:
            return self._config["options"].get("MQTT", {})
        # 직접 형식인 경우
        return self._config.get("MQTT", {})
    
    @property
    def topic_config(self) -> Dict[str, Any]:
        """Get topic configuration."""
        # Home Assistant 애드온 형식인 경우 options 내부에서 찾기
        if "options" in self._config:
            return self._config["options"].get("TOPIC", {})
        # 직접 형식인 경우
        return self._config.get("TOPIC", {})
    
    @property
    def mqtt_username(self) -> str:
        """Get MQTT username."""
        return self.mqtt_config.get("username", "")
    
    @property
    def mqtt_password(self) -> str:
        """Get MQTT password."""
        return self.mqtt_config.get("password", "")
    
    @property
    def mqtt_server(self) -> Optional[str]:
        """Get MQTT server address."""
        return self.mqtt_config.get("server")
    
    @property
    def mqtt_port(self) -> int:
        """Get MQTT port."""
        return self.mqtt_config.get("port", 1883)
    
    @property
    def root_topic(self) -> str:
        """Get root topic name."""
        return self.topic_config.get("root", "rs485_mqtt")
    
    @property
    def homeassistant_root_topic(self) -> str:
        """Get Home Assistant root topic name."""
        return self.topic_config.get("ha_root", "homeassistant")
    
    def validate_config(self) -> bool:
        """Validate required configuration values."""
        if not self.mqtt_server:
            self.logger.critical("치명적 오류: MQTT 서버 주소('server')가 설정되지 않았습니다. 애드온 구성을 확인하세요.")
            return False
        return True
    
    def print_config(self) -> None:
        """Print current configuration values."""
        if self.validate_config():
            self.logger.info("--- MQTT 설정 값 ---")
            self.logger.info(f"MQTT_USERNAME: {self.mqtt_username}")
            self.logger.info(f"MQTT_PASSWORD: {'*' * len(self.mqtt_password) if self.mqtt_password else ''}")
            self.logger.info(f"MQTT_SERVER: {self.mqtt_server}")
            self.logger.info(f"MQTT_PORT: {self.mqtt_port}")
            self.logger.info("--- TOPIC 설정 값 ---")
            self.logger.info(f"ROOT_TOPIC_NAME: {self.root_topic}")
            self.logger.info(f"HOMEASSISTANT_ROOT_TOPIC_NAME: {self.homeassistant_root_topic}")