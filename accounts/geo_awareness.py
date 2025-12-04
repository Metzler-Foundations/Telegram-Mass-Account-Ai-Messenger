#!/usr/bin/env python3
"""Geographic distribution awareness for accounts."""

import logging
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class GeoAwareness:
    """Tracks geographic distribution of accounts."""
    
    def __init__(self):
        self.account_locations: Dict[str, str] = {}
    
    def get_ip_location(self, ip_address: str) -> Optional[str]:
        """Get geographic location from IP address."""
        try:
            # Use ip-api.com (free, no key required)
            response = requests.get(
                f"http://ip-api.com/json/{ip_address}",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    country = data.get('countryCode', 'Unknown')
                    region = data.get('regionName', '')
                    city = data.get('city', '')
                    
                    location = f"{country}"
                    if region:
                        location += f"/{region}"
                    if city:
                        location += f"/{city}"
                    
                    return location
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get IP location: {e}")
            return None
    
    def check_ip_proxy_mismatch(self, account_id: str, expected_country: str, 
                                actual_ip: str) -> bool:
        """Check if IP location matches expected country."""
        location = self.get_ip_location(actual_ip)
        
        if not location:
            logger.warning(f"Could not verify location for {account_id}")
            return False
        
        # Extract country code
        country = location.split('/')[0]
        
        if country != expected_country:
            logger.warning(
                f"IP mismatch for {account_id}: "
                f"Expected {expected_country}, got {country}"
            )
            return True
        
        logger.debug(f"IP location verified for {account_id}: {location}")
        return False
    
    def get_distribution(self, account_ids: List[str]) -> Dict[str, int]:
        """Get geographic distribution of accounts."""
        distribution = {}
        
        for account_id in account_ids:
            location = self.account_locations.get(account_id, 'Unknown')
            distribution[location] = distribution.get(location, 0) + 1
        
        return distribution


_geo_awareness = None

def get_geo_awareness():
    global _geo_awareness
    if _geo_awareness is None:
        _geo_awareness = GeoAwareness()
    return _geo_awareness


