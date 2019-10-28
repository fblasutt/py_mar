#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This contains things relevant for setting up the model
"""

import numpy as np

from rw_approximations import rouw_nonst
from mc_tools import combine_matrices_two_lists, int_prob
from scipy.stats import norm
import sobol_seq
from collections import namedtuple

from scipy import sparse



class ModelSetup(object):
    def __init__(self,nogrid=False,divorce_costs='Default',**kwargs): 
        p = dict()        
        p['T']         = 7
        p['sig_zf_0']  = 0.15
        p['sig_zf']    = 0.05
        p['n_zf']      = 9
        p['sig_zm_0']  = 0.2
        p['sig_zm']    = 0.075
        p['n_zm']      = 5
        p['sigma_psi_init'] = 0.12
        p['sigma_psi']   = 2*0.03
        p['n_psi']     = 12
        p['beta'] = 0.95
        p['A'] = 1.2 # consumption in couple: c = (1/A)*[c_f^(1+rho) + c_m^(1+rho)]^(1/(1+rho))
        p['crra_power'] = 1.5
        p['couple_rts'] = 0.0       
        p['sig_partner_a'] = 0.1
        p['sig_partner_z'] = 0.2
        p['m_bargaining_weight'] = 0.5
        
        
        
        for key, value in kwargs.items():
            assert (key in p), 'wrong name?'
            p[key] = value
        
        
        p['nexo'] = p['n_zf']*p['n_zm']*p['n_psi']
        self.pars = p
        
        p_int = dict()
        
        
        # relevant for integration
        
        # this one is for (a_part,z_part,psi_couple)
        p_int['num_partners'] = 5
        p_int['nodes_couple'] = norm.ppf(sobol_seq.i4_sobol_generate(3,p_int['num_partners']))
        p_int['num_z_nodes'] = 7
        p_int['z_nodes'] = norm.ppf(sobol_seq.i4_sobol_generate(1,p_int['num_z_nodes']))
        p_int['large_3dim'] = norm.ppf(sobol_seq.i4_sobol_generate(3,30)) # generate many draws from normal
        self.integration = p_int
        
        
        self.state_names = ['Female, single','Male, single','Couple']
        
        
        if divorce_costs == 'Default':
            # by default the costs are set in the bottom
            self.div_costs = DivorceCosts()
        else:
            if isinstance(divorce_costs,dict):
                # you can feed in arguments to DivorceCosts
                self.div_costs = DivorceCosts(**divorce_costs)
            else:
                # or just the output of DivorceCosts
                assert isinstance(divorce_costs,DivorceCosts)
                self.div_costs = divorce_costs
            
        # exogrid should be deprecated
        if not nogrid:
        
            exogrid = dict()
            
            
            # let's approximate three Markov chains
            # this sets up exogenous grid
            exogrid['zf_t'],  exogrid['zf_t_mat'] = rouw_nonst(p['T'],p['sig_zf'],p['sig_zf_0'],p['n_zf'])
            exogrid['zm_t'],  exogrid['zm_t_mat'] = rouw_nonst(p['T'],p['sig_zm'],p['sig_zm_0'],p['n_zm'])
            exogrid['psi_t'], exogrid['psi_t_mat'] = rouw_nonst(p['T'],p['sigma_psi'],p['sigma_psi_init'],p['n_psi'])
            
            zfzm, zfzmmat = combine_matrices_two_lists(exogrid['zf_t'], exogrid['zm_t'], exogrid['zf_t_mat'], exogrid['zm_t_mat'])
            exogrid['all_t'], exogrid['all_t_mat'] = combine_matrices_two_lists(zfzm,exogrid['psi_t'],zfzmmat,exogrid['psi_t_mat'])
            exogrid['all_t_mat_sparse_T'] = [sparse.csc_matrix(D.T) if D is not None else None for D in exogrid['all_t_mat']]
            
            
            Exogrid_nt = namedtuple('Exogrid_nt',exogrid.keys())
            
            self.nexo = p['nexo']
            self.exogrid = Exogrid_nt(**exogrid)


        self.na = 60
        self.amin = 0
        self.amax = 20
        self.agrid = np.linspace(self.amin,self.amax,self.na)

        # grid for theta
        self.ntheta = 20
        self.thetamin = 0.01
        self.thetamax = 0.99
        self.thetagrid = np.linspace(self.thetamin,self.thetamax,self.ntheta)

        self.exo_grids = {'Female, single':exogrid['zf_t'],
                          'Male, single':exogrid['zm_t'],
                          'Couple':exogrid['all_t']}
        self.exo_mats = {'Female, single':exogrid['zf_t_mat'],
                          'Male, single':exogrid['zm_t_mat'],
                          'Couple':exogrid['all_t_mat']} # sparse version?
        
        
        # this pre-computes transition matrices for meeting a partner
        zf_t_partmat = [self.mar_mats(t,female=True) if t < p['T'] - 1 else None 
                            for t in range(p['T'])]
        zm_t_partmat = [self.mar_mats(t,female=False) if t < p['T'] - 1 else None 
                            for t in range(p['T'])]
        
        self.part_mats = {'Female, single':zf_t_partmat,
                          'Male, single':  zm_t_partmat,
                          'Couple': None} # last is added for consistency
        
        
    
    
    def mar_mats(self,t,female=True,trim_lvl=0.001):
        # TODO: check timing
        # this returns transition matrix for single agents into possible couples
        # rows are single's states
        # columnts are couple's states
        # you have to transpose it if you want to use it for integration
        setup = self
        
        nexo = setup.pars['nexo']
        sigma_psi_init = setup.pars['sigma_psi_init']
        sig_z_partner = setup.pars['sig_partner_z']
        psi_couple = setup.exogrid.psi_t[t+1]
        
        
        if female:
            nz_single = setup.exogrid.zf_t[t].shape[0]
            p_mat = np.empty((nexo,nz_single))
            z_own = setup.exogrid.zf_t[t]
            n_zown = z_own.shape[0]
            z_partner = setup.exogrid.zm_t[t+1]
            zmat_own = setup.exogrid.zf_t_mat[t]
        else:
            nz_single = setup.exogrid.zm_t[t].shape[0]
            p_mat = np.empty((nexo,nz_single))
            z_own = setup.exogrid.zm_t[t]
            n_zown = z_own.shape[0]
            z_partner = setup.exogrid.zf_t[t+1]
            zmat_own = setup.exogrid.zm_t_mat[t]    
            
        def ind_conv(a,b,c): return setup.all_indices((a,b,c))[0]
        
        
        for iz in range(n_zown):
            p_psi = int_prob(psi_couple,mu=0,sig=sigma_psi_init)
            if female:
                p_zm  = int_prob(z_partner, mu=z_own[iz],sig=sig_z_partner)
                p_zf  = zmat_own[iz,:]
            else:
                p_zf  = int_prob(z_partner, mu=z_own[iz],sig=sig_z_partner)
                p_zm  = zmat_own[iz,:]
            #sm = sf
        
            p_vec = np.zeros(nexo)
            
            for izf, p_zf_i in enumerate(p_zf):
                if p_zf_i < trim_lvl: continue
            
                for izm, p_zm_i in enumerate(p_zm):
                    if p_zf_i*p_zm_i < trim_lvl: continue
                
                    for ipsi, p_psi_i in enumerate(p_psi):                    
                        p = p_zf_i*p_zm_i*p_psi_i
                        
                        if p > trim_lvl:
                            p_vec[ind_conv(izf,izm,ipsi)] = p    
                            
            assert np.any(p_vec>trim_lvl), 'Everything is zero?'              
            p_vec = p_vec / np.sum(p_vec)
            p_mat[:,iz] = p_vec
            
        return p_mat.T # I
    
    
    def all_indices(self,ind_or_inds=None):
        
        # just return ALL indices if no argument is called
        if ind_or_inds is None: 
            ind_or_inds = np.array(range(self.pars['nexo']))
        
        if isinstance(ind_or_inds,tuple):
            izf,izm,ipsi = ind_or_inds
            ind = izf*self.pars['n_zm']*self.pars['n_psi'] + izm*self.pars['n_psi'] + ipsi
        else:
            ind = ind_or_inds
            izf = ind // (self.pars['n_zm']*self.pars['n_psi'])
            izm = (ind - izf*self.pars['n_zm']*self.pars['n_psi']) // self.pars['n_psi']
            ipsi = ind - izf*self.pars['n_zm']*self.pars['n_psi'] - izm*self.pars['n_psi']
            
        return ind, izf, izm, ipsi

    
    # functions u_mult and c_mult are meant to be shape-perservings
    
    def u_mult(self,theta):
        assert np.all(theta > 0) and np.all(theta < 1)
        powr = (1+self.pars['couple_rts'])/(self.pars['couple_rts']+self.pars['crra_power'])
        tf = theta
        tm = 1-theta
        ces = (tf**powr + tm**powr)**(1/powr)
        umult = (self.pars['A']**(1-self.pars['crra_power']))*ces
        
        
        
        assert umult.shape == theta.shape
        
        return umult
    
    
    def c_mult(self,theta):
        assert np.all(theta > 0) and np.all(theta < 1)
        powr = (1+self.pars['couple_rts'])/(self.pars['couple_rts']+self.pars['crra_power'])
        irho = 1/(1+self.pars['couple_rts'])
        irs  = 1/(self.pars['couple_rts']+self.pars['crra_power'])
        tf = theta
        tm = 1-theta
        bottom = (tf**(powr) + tm**(powr))**irho 
        
        kf = self.pars['A']*(tf**(irs))/bottom
        km = self.pars['A']*(tm**(irs))/bottom
        
        assert kf.shape == theta.shape
        assert km.shape == theta.shape
        
        return kf, km
    
    def u(self,c):
        return u_aux(c,self.pars['crra_power'])#(c**(1-self.pars['crra_power']))/(1-self.pars['crra_power'])
    
    def u_part(self,c,theta): # this returns utility of each partner out of some c
        kf, km = self.c_mult(theta)        
        return self.u(kf*c), self.u(km*c)
    
    def u_couple(self,c,theta): # this returns utility of each partner out of some c
        umult = self.u_mult(theta)        
        return umult*self.u(c)
    
    
    
    def vm_last(self,s,zm,zf,psi,theta,return_cs=False):
        # this is the value function for couple that has savings s,
        # Z = (zm,zf,psi) and bargaining power theta after all decisions are made
        
        income = s + np.exp(zm) +  np.exp(zf)
        kf, km = self.c_mult(theta)
        cf, cm = kf*income, km*income
        u_couple = self.u_mult(theta)*self.u(income)        
        u_m = self.u(cm)
        u_f = self.u(cf)
        V = u_couple + psi
        VM = u_m + psi
        VF = u_f + psi
        
        if return_cs:
            return V, VF, VM, income, np.zeros_like(income)
        else:
            return V, VF, VM

    def vm_last_grid(self,return_cs=False):
        # this returns value of vm on the grid corresponding to vm
        s_in = self.agrid[:,None,None]
        zm_in = self.exogrid.all_t[-1][:,1][None,:,None]
        zf_in = self.exogrid.all_t[-1][:,0][None,:,None]
        psi_in = self.exogrid.all_t[-1][:,2][None,:,None]
        theta_in = self.thetagrid[None,None,:]
                
        return self.vm_last(s_in,zm_in,zf_in,psi_in,theta_in,return_cs)
        
    
    

    def vs_last(self,s,z,return_cs=False):  
        # generic last period utility for single agent
        income = s+np.exp(z)
        if return_cs:
            return self.u(income), income, np.zeros_like(income)
        else:
            return self.u(income)
    
    def vs_last_grid(self,female,return_cs=False):
        # this returns value of vs on the grid corresponding to vs
        s_in = self.agrid[:,None]
        z_in = self.exogrid.zf_t[-1][None,:] if female else self.exogrid.zm_t[-1][None,:]
        return self.vs_last(s_in,z_in,return_cs)
        
    
    
    
    
    
    

#from numba import jit
#@jit(nopython=True)
def u_aux(c,sigma):
    # this is pretty important not to have (c^sigma - 1) here as it is hard to 
    # keep everywhere and occasionally this generates nasty mistakes
    if sigma!=1:
        return (c**(1-sigma))/(1-sigma)
    else:
        return np.log(c)

    


class DivorceCosts(object):
    # this is something that regulates divorce costs
    # it aims to be fully flexible
    def __init__(self, 
                 unilateral_divorce=True, # whether to allow for unilateral divorce
                 assets_kept = 0.9, # how many assets of couple are splited (the rest disappears)
                 u_lost_m=0.0,u_lost_f=0.0, # pure utility losses b/c of divorce
                 money_lost_m=0.0,money_lost_f=0.0, # pure money (asset) losses b/c of divorce
                 money_lost_m_ez=0.0,money_lost_f_ez=0.0 # money losses proportional to exp(z) b/c of divorce
                 ): # 
        
        self.unilateral_divorce = unilateral_divorce # w
        self.assets_kept = assets_kept
        self.u_lost_m = u_lost_m
        self.u_lost_f = u_lost_f
        self.money_lost_m = money_lost_m
        self.money_lost_f = money_lost_f
        self.money_lost_m_ez = money_lost_m_ez
        self.money_lost_f_ez = money_lost_f_ez