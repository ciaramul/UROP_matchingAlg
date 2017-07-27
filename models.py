from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
# import below for defining custom models: match to save the player-slot machine-payoff combinations
from otree.db.models import Model, ForeignKey
import random


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
        potPayoffs.add(random.lognormvariate(.75, .20))

    # assign payoffs to player ids in a group
    for p_id in range(1, Constants.players_per_group + 1):
        for sm_id in range(Constants.num_sm):
            # make an instance of Match with the given player id in group and slot machine
            pay = potPayoffs.pop()
            ForeignKey.Match.make_match(p_id, sm_id, pay)


class Constants(BaseConstants):
    name_in_url = 'SlotMachines'
    num_groups = 2

    instructions_template = 'matchingAlg/Instructions.html'\

    # Can manipulate the variables below
    players_per_group = 3
    num_rounds = 2
    num_sm = players_per_group + num_rounds

    payout_max = 1.00
    init_quit_pay = 1.50
    dec_quit_pay = .45


class Subsession(BaseSubsession):
    def before_session_starts(self):
        if self.round_number == 1:

            # assign groups
            self.group_randomly(fixed_id_in_group=True)

            # assign matching algorithm to each group
            groups = self.get_groups()
            for g in groups:
                g.vars['alg'] = random.choice(['fair', 'self', 'rand'])

            # cycle through groups to initially assign players to slot machines
            for g in groups:
                g.reassign(g.get_players())

        else:
            self.group_like_round(1)

            for g in self.get_groups():
                g.after_round()



class Group(BaseGroup):
    # Group means treatment group(but players are interacting), so fair or selfish matching algorithm applied
    alg = models.CharField()

    # Handle slot machines for checking players' options
    potSlots = list(range(Constants.num_sm))
    occupied = set()


    def after_round(self):
        switching = []
        players = self.get_players()

        for p in players:
            if p.statusActive:
                if p.offer_accepted == 3:
                    p.statusActive = False
                    self.occupied.remove(p.slotMachineCurrent) # sm no longer occupied
                    p.quit_payoff()
                elif p.offer_accepted == 2:
                    self.occupied.remove(p.slotMachineCurrent)
                    switching.append(p.id_in_group)
                    # will handle slot machine reassignment and payout in reassign funct below [greedy alg]
                elif p.offer_accepted == 1:
                    p.payout_accepted += p.payoff

        self.reassign(switching)

    def reassign(self, switching):          # use for initial matching and switching cases
        # reassign slot machines and provide payout for those switching
        groupSMavailable = []
        for sm_id in self.potSlots:
            if sm_id not in self.occupied:
                groupSMavailable.append(sm_id)

        for p2 in random.shuffle(switching):
            # parameters required are available slot machines
            playerSMavailable = []

            for sm_id in groupSMavailable:
                if sm_id not in p2.slotMachinesPrev:
                    if sm_id not in self.occupied:      # recheck for assignments of other switching players
                        playerSMavailable.append(sm_id)
            # payouts associated with different slot machines
            payouts = {}
            for sm_id in playerSMavailable:
                payouts[ForeignKey.Match.get_payoff( p2, sm_id)] = sm_id

            # reassign slot machines - add sm to occupied and change p2's value for currentSM
            if self.alg == 'fair':
                # need to make probabilistic, but deterministic for now
                newSMpay = max(payouts.keys())
            elif self.alg == 'rand':
                newSMpay = random.choice (payouts.keys())
            elif self.alg == 'self':
                newSMpay = random.choice(payouts.keys())    # change this later

            slotMach_id = payouts[newSMpay]
            p2.slotMachineCurrent = slotMach_id  # assign sm to player
            self.occupied.add(slotMach_id)        # note that sm is now occupied
            p2.slotMachinesPrev.append(slotMach_id)     #note that player cannot return to this sm

            # payout the payoffs
            p2.payoff = ForeignKey.Match.get_payoff(p2.id_in_group, p2.slotMachineCurrent)


class Player(BasePlayer):
    statusActive = models.BooleanField(initial = True)

    slotMachineCurrent = models.PositiveIntegerField()

    # for Player.offer_accepted variable, 1 = return, 2 = switch, 3 = quit game
    offer_accepted = models.PositiveIntegerField(
        choices=[
            [1, 'Return to same slot machine'],
            [2, 'Switch slot machines'],
            [3, 'Quit this game'],
        ], initial = 2
    )

    # record the slot machine ids with which the player has matched
    slotMachinesPrev = set()

    def quit_payoff(self):
        if Subsession.round_number == 1:
            self.participant.payoff = Constants.init_quit_pay
        else:
            self.participant.payoff += Constants.init_quit_pay - (Subsession.round_number - 1)* Constants.dec_quit_pay

