from otree.api import Currency as c, currency_range
from . import models
from ._builtin import Page, WaitPage
from .models import Constants
from .models import Constants, Decision
from django.forms import modelformset_factory


class MyPage(Page):
    """Description of the game: How to play and potential returns"""
    pass


class ResultsOptions(Page):
    """Player: Choose whether to return, switch, or quit slot machines"""

    form_model = models.Player
    form_fields = ['offer_accepted']

    timeout_seconds = 60
    timeout_submission = {'offer_accepted': 3}



class ResultsWaitPage(WaitPage):

    def after_all_players_arrive(self):
        pass




page_sequence = [
    MyPage,
    ResultsOptions,
    ResultsWaitPage
]
