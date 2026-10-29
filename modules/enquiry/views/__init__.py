# modules/enquiry/views/__init__.py
from modules.enquiry.views.enquiry_home import EnquiryHome
from modules.enquiry.views.enquiry_form_modal import EnquiryFormModal
from modules.enquiry.views.quick_enquiry_modal import QuickEnquiryModal
from modules.enquiry.views.follow_up_dialog import EnquiryFollowUpDialog

__all__ = ["EnquiryHome", "EnquiryFormModal", "QuickEnquiryModal", "EnquiryFollowUpDialog"]
