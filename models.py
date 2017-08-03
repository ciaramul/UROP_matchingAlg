from otree.api import (
    models, widgets, BaseConstants, BaseSubsession, BaseGroup, BasePlayer,
    Currency as c, currency_range
)
# import below for defining custom models: match to save the player-slot machine-payoff combinations
from otree.db.models import Model, ForeignKey
from django.contrib.postgres.fields import ArrayField
import random, numpy
import copy

author = 'Ciara Mulcahy'

doc = """
This is a multi-period slot machine game with 3 [var] players.
Each round, every player selects whether to 
remain at the same slot machine, switch slot machines, or quit the game entirely. 
"""


class Constants(BaseConstants):
    name_in_url = 'SlotMachines'
    num_groups = 3

    instructions_template = 'matchingAlg/Instructions.html'\

    # Can manipulate the variables below
    players_per_group = 3
    num_rounds = 2
    num_sm = players_per_group + num_rounds
    potSlots = list(range(num_sm))

    payout_max = 100
    sd_payoffs = 20
    init_quit_pay = 150
    dec_quit_pay = 45

'''
class PayEntry(Model):
    key = models.PositiveIntegerField()
    payoff_amt = models.CurrencyField()
    visit_times = models.IntegerField(initial=0)
    switch_from_times = models.IntegerField(initial=0)

    subsession = ForeignKey(Subsession)
'''

class Subsession(BaseSubsession):
    '''
    def gen_payoff_stubs(self):     # generate data structure of potential payoffs
        for _ in range(Constants.num_sm):
            payentry = self.session.vars.payentry_set.create()
            payentry.payoff_amt = random.randint(0, 100)
            payentry.key = _
            payentry.save()
    '''

    def before_session_starts(self):
        rounds_remaining = Constants.num_rounds - self.round_number
        if self.round_number == 1:
            # assign players to groups
            self.group_randomly(fixed_id_in_group=True)

            self.session.vars['payoff_dict'] = {}
            init_switch_from = [0,0]
            for _ in range(Constants.num_sm):
                self.session.vars['payoff_dict'][numpy.random.randint(low=0, high=100)] = init_switch_from


            # assign payoffs to player ids in a group
            for p_id in range(1, Constants.players_per_group + 1):
                # regenerate the potential payouts between players, should not affect session.vars
                player_pay = self.session.vars['payoff_dict'].keys()

                for sm_id in range(1, Constants.num_sm + 1):
                    # make an instance of Match with the given player id in group and slot machine

                    pay = numpy.random.choice(list(player_pay), replace=False)

                    for g in self.get_groups():
                        p = g.get_player_by_id(p_id)
                        p.make_sm_match(sm_id, pay)

            # assign matching algorithm to each group
            groups = self.get_groups()
            for g in groups:
                g.alg = numpy.random.choice(['fair', 'self', 'rand'], replace = False)

            # cycle through groups to initially assign players to slot machines
            for g in groups:
                for p in g.get_players():
                    p.participant.vars['slotMachinesPrev'] = set()
                all_switching = list(range(1, Constants.players_per_group+1))
                g.reassign(all_switching)

        else:
            self.group_like_round(1)

            for g in self.get_groups():
                g.after_round()


class Group(BaseGroup):
    # Group means treatment group(but players are interacting), so fair or selfish matching algorithm applied
    alg = models.CharField()

    # Handle slot machines for checking players' options

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
                    self.session.vars['payoff_dict'][p.payoffCurrent][0] += 1
                elif p.offer_accepted == 1:
                    p.payout_accepted += p.payoff
                    self.session.vars['payoff_dict'][p.payoffCurrent][-1] += 1      # fix these counts later

        self.reassign(switching)

    def reassign(self, switching):          # use for initial matching and switching cases
        # reassign slot machines and provide payout for those switching
        # work around to store group's variable lists and sets

        data_store_player = self.get_player_by_id(1)

        data_store_player.participant.vars['groupSMavailable'] = []
        sm_available = data_store_player.participant.vars['groupSMavailable']
        data_store_player.participant.vars['occupied'] = set()
        occupied = data_store_player.participant.vars['occupied']

        for sm_id in Constants.potSlots:
            if sm_id not in occupied:
                sm_available.append(sm_id)

        random.shuffle(switching)   # shuffle order of switching player ids
        for p_id in switching:
            p2 = self.get_player_by_id(p_id)

            # parameters required are available slot machines
            p2.participant.vars['playerSMavailable'] = []
            for sm_id in sm_available:
                if sm_id not in p2.participant.vars['slotMachinesPrev']:
                    if sm_id not in data_store_player.participant.vars['occupied']:      # recheck for assignments of other switching players
                        p2.participant.vars['playerSMavailable'].append(sm_id)

            # payouts associated with different slot machines
            data_store_player.participant.vars['payouts'] = {}
            payouts = data_store_player.participant.vars['payouts']
            for sm_id in p2.participant.vars['playerSMavailable']:
                sm_current = Match.objects.filter(slot_machine_id = sm_id, player_id_in_group = p_id)[0]
                pay_amt = sm_current.get_pay()
                payouts[pay_amt] = sm_id

            # reassign slot machines - add sm to occupied and change p2's value for currentSM
            if self.alg == 'fair':
                # need to make probabilistic, but deterministic for now
                newSMpay = max(payouts.keys())
            elif self.alg == 'rand':
                newSMpay = random.choice(payouts.keys())
            elif self.alg == 'self':
                newSMpay = random.choice(payouts.keys())    # change this later

            slotMach_id = payouts[newSMpay]
            p2.slotMachineCurrent = slotMach_id  # assign sm to player
            self.occupied.add(slotMach_id)        # note that sm is now occupied
            p2.participant.vars['slotMachinesPrev'].add(slotMach_id)     # note that player cannot return to this sm

            # payout the payoffs
            p2.payoff = newSMpay


class Player(BasePlayer):
    statusActive = models.BooleanField(initial = True)

    def make_sm_match(self, sm_id, pay):
        if not self.match_set:
            match = self.match_set.create(slot_machine_id = sm_id, mean_payoff = pay)
            match.save()  # save to DB
        else:
            self.match_set.add(Match(slot_machine_id = sm_id, mean_payoff = pay))

    slotMachineCurrent = models.PositiveIntegerField()
    payoffCurrent = models.CurrencyField()

    # for Player.offer_accepted variable, 1 = return, 2 = switch, 3 = quit game
    offer_accepted = models.PositiveIntegerField(
        choices=[
            [1, 'Return to same slot machine'],
            [2, 'Switch slot machines'],
            [3, 'Quit this game'],
        ], initial = 2
    )

    # record the slot machine ids with which the player has matched as self.participant.vars['slotMachinesPrev']

    # linear decrease in quitting payout across rounds
    def quit_payoff(self):
        if Subsession.round_number == 1:
            self.participant.payoff = Constants.init_quit_pay
        else:
            self.participant.payoff += Constants.init_quit_pay - (Subsession.round_number - 1)* Constants.dec_quit_pay


class Match(Model):
    # Match means a potential combination of a slot machine and a player

    mean_payoff = models.FloatField()
    slot_machine_id = models.PositiveIntegerField()
    player_id_in_group = models.PositiveIntegerField()

    def get_pay(self):
        # player_id = group.get_player_by_id(id_num)
        pay = numpy.random.normal(loc = self.mean_payoff, scale = Constants.sd_payoffs)
        return pay

    player = ForeignKey(Player)

