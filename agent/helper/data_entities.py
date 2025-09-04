import json
from dataclasses import dataclass, asdict
from typing import Optional
from livekit.agents import JobContext, BackgroundAudioPlayer

@dataclass
class UserData:
    "Class to store user and service data during the call"
    ctx: Optional[JobContext] = None

    # info
    name: Optional[str] = None
    contact_number: Optional[str] = None
    interested_in_offer: Optional[str] = None
    have_driving_license: Optional[str] = None
    driven_uber_before: Optional[str] = None
    is_user_id_active: Optional[str] = None
    city: Optional[str] = None
    is_valid_city: Optional[bool] = None
    customer_location: Optional[str] = None
    customer_preferred_day: Optional[str] = None

    bg_player: BackgroundAudioPlayer = None
    
    def is_identified(self) -> bool:
        """Check if the customer is identified."""
        return self.full_name is not None

    def summarize(self) -> str:
        """Return a human-readable summary of user data."""
        return (
            f"Name: {self.name or '-'}\n"
            f"Contact Number: {self.contact_number or '-'}\n"
            f"Interested in Offer: {self.interested_in_offer or '-'}\n"
            f"Have Driving License: {self.have_driving_license or '-'}\n"
            f"Driven Uber Before: {self.driven_uber_before or '-'}\n"
            f"Is User ID Active: {self.is_user_id_active or '-'}\n"
            f"City: {self.city or '-'}\n"
            f"Customer Location: {self.customer_location or '-'}"
        )

    # def summarize(self) -> str:
    #     """Return contents of self object in pretty string format."""
    #     return json.dumps(asdict(self), indent=4, ensure_ascii=False)
    