from otree.api import Currency as c, currency_range
from . import models
from ._builtin import Page, WaitPage
from .models import Constants
import json


class MyPage(Page):
    """Description of the game: How to play and potential returns"""
    def is_displayed(self):
        return self.round_number == 1

    def vars_for_template(self):
        return {'main_image_path': "matchingAlg\main1.jpg"}


class ResultsWaitPage(Page):
    def is_displayed(self):
        return self.round_number != 1 and self.player.participant.vars.get('statusActive')

    def after_all_players_arrive(self):
        self.group.before_next_round()

    def vars_for_template(self):
        return {'status': self.player.in_round(self.round_number-1).offer_accepted,
                'image_path': "matchingAlg\play{}.jpg".format(self.player.in_round(self.round_number-1).offer_accepted),
                }


class ResultsOptions(Page):
    """Player: Choose whether to return, switch, or quit slot machines"""
    def vars_for_template(self):
        with open("matchingAlg/static/matchingAlg/image_credits.json") as source:
            credit_source = json.loads(source.read())
        return {'balance': sum([p.payoff for p in self.player.in_all_rounds()]),
                'rounds_remaining': Constants.num_rounds - self.round_number,
                'image_path': "matchingAlg/{}.jpg".format(self.player.current_slot_machine_id),
                'image_credit': credit_source[str(self.player.current_slot_machine_id)],
                'quit_pay': self.player.quit_payoff()
                }

    form_model = models.Player
    form_fields = ['offer_accepted']

    timeout_seconds = Constants.timeout_seconds
    timeout_submission = {'offer_accepted': 3}  # player quits if times out

    def is_displayed(self):
        return self.player.participant.vars.get('statusActive')


page_sequence = [
    MyPage,
    ResultsWaitPage,
    ResultsOptions
]
