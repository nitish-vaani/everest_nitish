"""
GreeterAgent
-> checks "interested_in_job"
    -> Yes -> DisInteretHandlerAgent
    -> No -> IntakeUserInfoAgent

DisInteretHandlerAgent
-> sells
    -> if becomes interested: 
        -> stores customer_location_in_preferred_city and _book_an_appointment
    -> else 
        -> hungs up

IntakeUserInfoAgent
-> valid_driving_license, driven_uber_before, is_uber_id_active, city_interested
-> if valid_driving_license:
    -> AppointmentSchedulerAgent
-> else:
    -> hungup the call

AppointmentSchedulerAgent
-> customer_location_in_preferred_city, _book_an_appointment
-> if booking done:
    -> hung up
"""