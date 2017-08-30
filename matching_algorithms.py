import numpy as np
from scipy.optimize import minimize
from scipy.optimize import linear_sum_assignment
import matplotlib.pyplot as plt

# called to initialize for each super group's combinations set
def correlated_payoffs(n_sm, nplayers):
	# n = number of slot machines
	# Correlated distribution
	payoffs = []
	
	base = np.random.beta(1, 2, size=n_sm)*20 

	for i in range(nplayers):		# changed indexing here
		sm_d = {}
		p = np.random.normal(0.0, 3.0, size=n_sm)
		pay = base + p
		pay = normalize_payoff(pay)

		for j in range(n_sm):
			sm_d[j]=pay[j]
		payoffs.append(sm_d)

	return payoffs	# list with nplayers number of dictionaries


 # Input: partial dictionary with payoffs
 # nslots = slot machines per user
def payoff_matrix(payoffs, nslots, nplayers):
	matrix = []
	for p_id in range(nplayers):
		p = [-10000.0 for i in range(nslots)] # assign negative weight to unavailable slots
		if p_id in payoffs.keys():
			sm_pay_dict = payoffs[p_id]
			for sm_id in sm_pay_dict.keys():
				p[sm_id] = sm_pay_dict[sm_id]
		matrix.append(p)
	return np.array(matrix)		


# Fair matching assignation	
def fair_matching(payoffs, nslots, nplayers):
	payoff = payoff_matrix(payoffs, nslots, nplayers)
	cost = -1*payoff
	row_ind, col_ind = linear_sum_assignment(cost)
	pays = []
	for i in range(len(row_ind)):
		pays.append(payoff[row_ind[i], col_ind[i]])
		
	return row_ind, col_ind, pays



# prob = dictionary with probability of switching as a function of payoff
def probability_matrix(payoffs, nslots, nplayers, prob):
	payoff_mat = payoff_matrix(payoffs, nslots, nplayers)

	matrix = [[-10000.0 for i in range(nslots)] for i in range(nplayers)]
	for i in range(nplayers):
		for j in range(nslots):
			p = payoff_mat[i][j]
			if p >=0:
				matrix[i][j]= prob[p]/ (1 + prob[p])
	return np.array(matrix)


# Selfish Matching assignation
def self_matching(payoffs, nslots, nplayers, q):
	prob = probability_matrix(payoffs, nslots, nplayers, q)
	payoff = payoff_matrix(payoffs, nslots, nplayers)
	null_prob = -1*prob
	player_ind, sm_ind = linear_sum_assignment(null_prob)

	pays = []
	for i in range(len(player_ind)):
		pays.append(payoff[player_ind[i], sm_ind[i]])
	
	return player_ind, sm_ind, pays



def normalize_payoff(p):
	p = np.floor(p)
	p_norm = np.clip(p, 0, 20)
	# raise ValueError("this is %r" %(p_norm))
	return p_norm


def initialize_probs():
	q = {}
	for i in range(21):
		q[i] = i/20.0 *(1-i/20.) * 4 #x(1-x)

	return q


## IID Beta Distribution 
# payoffs = []
# for i in range(nplayers):
# 	d = {}
# 	p = np.random.beta(1, 2, size=n)*20 #1,2
# 	p = normalize_payoff(p,2.0)
# 	# plt.hist(p)
# 	# plt.show()
# 	for j in range(n):
# 		d[j]=p[j]
# 	payoffs.append(d)

#fair_matching(payoffs, n)










#self_matching(payoffs, n, q)



