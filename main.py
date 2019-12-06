#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aCreated on Tue Sep 17 19:14:08 2019

@author: Egor Kozlov
"""


if __name__ == '__main__':
    
    
    #Clean Memory
    try:
        from IPython import get_ipython
        get_ipython().magic('reset -f')
    except:
        pass
 
    #import numpy as np
    from model import Model
    from setup import DivorceCosts
  
    

    dc = DivorceCosts(unilateral_divorce=False,assets_kept = 1.0,u_lost_m=0.02,u_lost_f=0.02,eq_split=0.0)
    sc = DivorceCosts(unilateral_divorce=True,assets_kept = 1.0,u_lost_m=0.00,u_lost_f=0.00)
    #Solve the model
    mdl = Model(iterator_name='default-timed',
                divorce_costs=dc,separation_costs=sc)
    
    graphs=True
    #gassets,iexo,state,gtheta=mdl.solve_sim()
    mdl.solve_sim(simulate=True,Prof=True)
    #gassets, iexo, state, gtheta = mdl.agents.gsavings_c, mdl.agents.iexo, mdl.agents.state, mdl.agents.gtheta
    mdl.time_statistics()
    
    
    #Graphs Here
    
    
    #Indexes for the graphs
    if graphs:
        ai=0
        zfi=0
        zmi=4
        psii=5
        ti=0
        thi=10
        
        #Actual Graphs
        mdl.graph(ai,zfi,zmi,psii,ti,thi)
        
        #If you plan to use graphs only once, deselect below to save space on disk
        #os.remove('name_model.pkl') 
    


   
        


    