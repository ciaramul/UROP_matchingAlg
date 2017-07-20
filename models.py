from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
# import below for defining custom models: match to save the player-slot machine-payoff combinations
from otree.db.models import Model, ForeignKey


author = 'Ciara Mulcahy'

doc = """
This is a multi-period slot machine game with 3 [var] players.
Each round, every player selects whether to 
remain at the same slot machine, switch slot machines, or quit the game entirely. 
"""
class Match(Model):
    # Match means a potential combination of a slot machine and a player
    # applied = models.BooleanField()

    def make_match(self, player_id_num, slot_machine_id, payoff_amt):
        self.payoff = payoff_amt
        self.slot_machine_id = slot_machine_id
        self.player_id_in_group = player_id_num

    def get_payoff(self, player_id_num, slot_machine_id ):
        # player_id = group.get_player_by_id(id_num)
        return self.payoff

# define variables global to the session (player_id_in_group-slot machine-payoff combinations)
def assign_payoffs(self):
    # generate set of potential payoffs
    potPayoffs = set()
    for s in range(1, Constants.num_sm + 1):
        potPayoffs.add(random.randfloat())

    # assign payoffs to player ids in a group
    rankings = {}       # rn for deterministic case, might change for probabilistic
    for p_id in range(1, Constants.players_per_group + 1):
        tempList = []
        for sm_id in range(Constants.num_sm):
            # make an instance of Match with the given player id in group and slot machine
            pay = potPayoffs.pop()
            Match.make_match(p_id, sm_id, pay )
            tempList.append(Match.get_payoff(p_id, sm_id))
        # Make a dictionary ranking the advantageousness of each sm for a player id
        rankings[p_id] = sorted(tempList)


class Constants(BaseConstants):
    name_in_url = 'SlotMachines'
    num_groups = 2

    instructions_template = 'matchingAlg/Instructions.html'\

    # Can manipulate the variables below
    players_per_group = 3
    num_rounds = 2
    num_sm = players_per_group + num_rounds

    payout_max = 1.00
    quit_pay = 1.50


class Subsession(BaseSubsession):
    def before_session_starts(self):
        if self.round_number == 1:
            # the players can be associated with payoff permanently and participants
            #   can decide each round if they are switching players or not

            # assign groups
            self.group_randomly(fixed_id_in_group=True)

            for p in self.get_players():
                p.participant.vars['alg'] = random.choice(['fair', 'self'])
            groups = self.get_groups()

            # cycle through groups to assign payoffs to play
            for g in groups:
                for p in g.get_players():
                    p.payoff = Match.get_payoff(p.id_in_group, p.slotMachineCurrent)

        else:
            self.group_like_round(1)

            for g in self.get_groups():
                g.after_round()



class Group(BaseGroup):
    # Group means treatment group(but players are interacting), so fair or selfish matching algorithm applied
    alg = models.CharField()

    def after_round(self):
        players = self.get_players()

        for p in players:
            if p.statusActive:
                if p.offer_accepted == 3:
                    p.statusActive = False
                    p.quit_payoff()
                elif p.offer_accepted == 2:
                    if self.alg == 'Fair':
                        # need to make probabilistic, but deterministic for now

                    elif self.alg == 'Selfish':


                    # insert some slot machine switching code
                        # new slot machine must be unoccupied
                    p.payoff = Match.get_payoff(p.id_in_group, p.slotMachineCurrent)
                elif p.offer_accepted == 1:
                    p.payout_accepted += p.payoff


class Player(BasePlayer):
    statusActive = models.BooleanField(initial = True)

    slotMachineCurrent = models.PositiveIntegerField()

    # for Player.offer_accepted variable, 1 = return, 2 = switch, 3 = quit game
    offer_accepted = models.PositiveIntegerField(
        choices=[
            [1, 'Return to same slot machine'],
            [2, 'Switch slot machines'],
            [3, 'Quit this game'],
        ]
    )

    # make the matching with players and sm implementation in views.py

    def quit_payoff(self):
        self.participant.payoff = Constants.quit_pay


class SlotMachine(Model):
    group = ForeignKey(Group)
    id = models.PositiveIntegerField()
    occupied = models.BooleanField()

    # record the player ids with which the slot machine has matched
    players = []






