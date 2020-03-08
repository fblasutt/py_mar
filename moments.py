# -*- coding: utf-8 -*-   
"""   
Created on Thu Nov 14 10:26:49 2019   
    
This file comupte simulated moments + optionally   
plots some graphs   
    
@author: Fabio   
"""   
    
import numpy as np   
import matplotlib.pyplot as plt   
#from matplotlib.pyplot import plot, draw, show   
import matplotlib.backends.backend_pdf   
from statutils import strata_sample
 
#For nice graphs with matplotlib do the following 
matplotlib.use("pgf") 
matplotlib.rcParams.update({ 
    "pgf.texsystem": "pdflatex", 
    'font.family': 'serif', 
    'font.size' : 11, 
    'text.usetex': True, 
    'pgf.rcfonts': False, 
}) 
 
 
import pickle   
import pandas as pd   
import statsmodels.api as sm   
import statsmodels.formula.api as smf   
  
    
def moment(mdl,agents,agents_male,draw=True,validation=False):   
#This function compute moments coming from the simulation   
#Optionally it can also plot graphs about them. It is feeded with   
#matrixes coming from simulations   
    

    
    #Import simulated values   
    assets_t=mdl.setup.agrid_c[agents.iassets] # FIXME   
    iexo=agents.iexo   
    state=agents.state   
    theta_t=mdl.setup.thetagrid_fine[agents.itheta]   
    setup = mdl.setup  
    female=agents.is_female
    cons=agents.c
    consx=agents.x
    labor=agents.ils_i
    shks = agents.shocks_single_iexo 
    
    
    #Import values for female labor supply (simulated men only)
    state_psid=agents_male.state
    labor_psid=agents_male.ils_i
    change_psid=agents_male.policy_ind
    iexo_w=agents.iexo 
    labor_w=agents.ils_i
    female_w=agents.is_female
    state_w=agents.state 
    theta_w=mdl.setup.thetagrid_fine[agents.itheta] 
    assets_w=mdl.setup.agrid_c[agents.iassets]
    changep_w=agents.policy_ind 

           
           
    moments = dict()   
        
        
    ##########################################   
    #START COMPUTATION OF SIMULATED MOMENTS   
    #########################################   
      
        
    #Create a file with the age of the change foreach person   
    changep=agents.policy_ind  
       
        
    #Get states codes   
    state_codes = {name: i for i, name in enumerate(mdl.setup.state_names)}   
      
     ###########################################   
    #Sample selection   
    ###########################################   
       
    #Sample Selection to replicate the fact that   
    #in NSFH wave two cohabitning couples were   
    #excluded.   
    #Birth cohorts: 45-55   
    #Second wave of NLSFH:1992-1994.   
    #   
    #Assume that people are interviewd in 1993 and that age is uniformly   
    #distributed. Clearly we can adjust this later on.   
       
       
       
    #First cut the first two periods give new 'length'   
    assets_t=assets_t[:,0:mdl.setup.pars['T']]   
    iexo=iexo[:,0:mdl.setup.pars['T']]   
    state=state[:,0:mdl.setup.pars['T']]   
    theta_t=theta_t[:,0:mdl.setup.pars['T']]   
    female=female[:,0:mdl.setup.pars['T']]   
    labor_psid=labor_psid[:,0:mdl.setup.pars['T']]
    iexo_w=iexo_w[:,0:mdl.setup.pars['T']]
    labor_w=labor_w[:,0:mdl.setup.pars['T']]
    change_psid=change_psid[:,0:mdl.setup.pars['T']]
    state_psid=state_psid[:,0:mdl.setup.pars['T']]
    female_w=female_w[:,0:mdl.setup.pars['T']]
    state_w=state_w[:,0:mdl.setup.pars['T']]
    assets_w=assets_w[:,0:mdl.setup.pars['T']]
    theta_w=theta_w[:,0:mdl.setup.pars['T']]
    changep_w=changep_w[:,0:mdl.setup.pars['T']]
      
       
    ####################################################################   
    #Now drop observation to mimic the actual data gathering process   
    ####################################################################   
       
    #Get distribution of age conditional on cohabiting on the second wave   
    with open('age_sw.pkl', 'rb') as file:   
        age_sw=pickle.load(file)   
           
    keep=(assets_t[:,0]>-1)   
      
   
    summa=0.0   
    summa1=0.0   
    for i in age_sw:   
        summa+=age_sw[i]   
        keep[int(summa1*len(state[:,0])/sum(age_sw.values())):int(summa*len(state[:,0])/sum(age_sw.values()))]=(state[int(summa1*len(state[:,0])/sum(age_sw.values())):int(summa*len(state[:,0])/sum(age_sw.values())),int((i-20)/mdl.setup.pars['py'])]!=3)   
         
        summa1+=age_sw[i]   
   
    
    state=state[keep,]    
    changep=changep[keep,] 
    female=female[keep,] 
    iexo=iexo[keep,]
    assets_t=assets_t[keep,]
    labor=labor[keep,]
    
      
    
    ###################################################################
    # Draw from simulated agents to match NSFH distribution
    # according to the following stratas:
    # 1) Age at unilateral divorce
    # 2) Gender
    # 
    ###################################################################
    
    #Import the distribution from the data
    with open('freq_nsfh.pkl', 'rb') as file:   
        freq_nsfh_data=pickle.load(file)  
    
    #Make data compatible with current age
    freq_nsfh_data['age_unid']=freq_nsfh_data['age_unid']-18.0
    freq_nsfh_data.loc[freq_nsfh_data['age_unid']<=0.0,'age_unid']=0.0
    freq_nsfh_data.loc[freq_nsfh_data['age_unid']>=900.0,'age_unid']=1000
    
    #Drop if no change in law!
    if np.all(changep==0):
        freq_nsfh_data.loc[freq_nsfh_data['age_unid']<1910.0,'age_unid']=1000
   
 
        
    freq_nsfh=freq_nsfh_data.groupby(['M2DP01','age_unid'])['SAMWT'].count()
    #Create a Dataframe with simulated data to perform the draw
    age_unid=np.argmax(changep,axis=1)
    never=(changep[:,0]==0) & (age_unid[:]==0)
    age_unid[never]=1000
    age_unid[changep[:,-1]==0]=1000
    
    fem=np.array(['FEMALE']*len(female))
    fem[female[:,0]==0]='MALE'
    
    inde=np.linspace(1,len(fem),len(fem),dtype=np.int32)
    
    ddd=np.stack((inde,age_unid,fem),axis=0).T
    df=pd.DataFrame(data=ddd,columns=["Index","age","sex"],index=ddd[:,0])
    df['age']=df['age'].astype(np.float)
    
    sampletemp=strata_sample(["'sex'", "'age'"],freq_nsfh,frac=0.6,tsample=df,distr=True)
    final2=df.merge(sampletemp,how='left',on='Index',indicator=True)
    
    keep2=[False]*len(df)
    keep2=(np.array(final2['_merge'])=='both')
    
    #Keep again for all relevant variables   
    state=state[keep2,]     
    changep=changep[keep2,] 
    female=female[keep2,]
    iexo=iexo[keep2,]
    assets_t=assets_t[keep2,]
    labor=labor[keep2,]
  
    
    #Initial distribution
    prima=freq_nsfh/np.sum(freq_nsfh)
    
    #Final distribution
    final3=df[keep2]
    final4=final3.groupby(['sex','age'])['sex'].count()
    dopo=final4/np.sum(final4)
    
    
    print('The average deviation from actual to final ditribution is {:0.2f}%'.format(np.mean(abs(prima-dopo))*100))
    ###################################################################  
    #Get age we stop observing spells: this matters for hazards
    ###################################################################  
    with open('age_sint.pkl', 'rb') as file:   
        age_sint=pickle.load(file)   
           
    aged=np.ones((state.shape))  
      
   
    summa=0.0  
    summa1=0.0  
    for i in age_sint:  
        summa+=age_sint[int(i)]  
        aged[int(summa1*len(aged[:])/sum(age_sint.values())):int(summa*len(aged[:])/sum(age_sint.values()))]=round((i-20)/mdl.setup.pars['py'],0)  
        summa1+=age_sint[int(i)]  
      
    aged=np.array(aged,dtype=np.int16)  
    ###########################################   
    #Moments: Construction of Spells   
    ###########################################   
    nspells = (state[:,1:]!=state[:,:-1]).astype(np.int).sum(axis=1).max() + 1  
    index=np.array(np.linspace(1,len(state[:,0]),len(state[:,0]))-1,dtype=np.int16)  
    N=len(iexo[:,0])  
    state_beg = -1*np.ones((N,nspells),dtype=np.int8)   
    time_beg = -1*np.ones((N,nspells),dtype=np.bool)   
    did_end = np.zeros((N,nspells),dtype=np.bool)   
    state_end = -1*np.ones((N,nspells),dtype=np.int8)   
    time_end = -1*np.ones((N,nspells),dtype=np.bool)   
    sp_length = -1*np.ones((N,nspells),dtype=np.int16)   
    sp_person = -1*np.ones((N,nspells),dtype=np.int16)   
    is_unid = -1*np.ones((N,nspells),dtype=np.int16)   
    is_unid_end = -1*np.ones((N,nspells),dtype=np.int16)   
    is_unid_lim = -1*np.ones((N,nspells),dtype=np.int16)   
    n_spell = -1*np.ones((N,nspells),dtype=np.int16)   
    is_spell = np.zeros((N,nspells),dtype=np.bool)   
      
        
    state_beg[:,0] = 0 # THIS ASSUMES EVERYONE STARTS AS SINGLE   #TODO consistent with men stuff?
    time_beg[:,0] = 0   
    sp_length[:,0] = 1   
    is_spell[:,0] = True   
    ispell = np.zeros((N,),dtype=np.int8)   
        
    for t in range(1,mdl.setup.pars['T']):   
        ichange = ((state[:,t-1] != state[:,t]))   
        sp_length[((~ichange)),ispell[((~ichange))]] += 1   
        #ichange = ((state[:,t-1] != state[:,t]) & (t<=aged[:,t]))   
        #sp_length[((~ichange) & (t<=aged[:,t])),ispell[((~ichange) & (t<=aged[:,t]))]] += 1   
            
        if not np.any(ichange): continue   
            
        did_end[ichange,ispell[ichange]] = True   
            
        is_spell[ichange,ispell[ichange]+1] = True   
        sp_length[ichange,ispell[ichange]+1] = 1 # if change then 1 year right   
        state_end[ichange,ispell[ichange]] = state[ichange,t]   
        sp_person[ichange,ispell[ichange]] = index[ichange]  
        time_end[ichange,ispell[ichange]] = t-1   
        state_beg[ichange,ispell[ichange]+1] = state[ichange,t]    
        time_beg[ichange,ispell[ichange]+1] = t   
        n_spell[ichange,ispell[ichange]+1]=ispell[ichange]+1  
        is_unid[ichange,ispell[ichange]+1]=changep[ichange,t]  
        is_unid_lim[ichange,ispell[ichange]+1]=changep[ichange,aged[ichange,0]]  
        is_unid_end[ichange,ispell[ichange]]=changep[ichange,t-1]  
          
            
        ispell[ichange] = ispell[ichange]+1   
            
            
    allspells_beg = state_beg[is_spell]   
    allspells_len = sp_length[is_spell]   
    allspells_end = state_end[is_spell] # may be -1 if not ended   
    allspells_timeb = time_beg[is_spell]  
    allspells_isunid=is_unid[is_spell]  
    allspells_isunidend=is_unid_end[is_spell]  
    allspells_isunidlim=is_unid_lim[is_spell]  
    allspells_person=sp_person[is_spell]  
    allspells_nspells=n_spell[is_spell]  
      
      
        
    # If the spell did not end mark it as ended with the state at its start   
    allspells_end[allspells_end==-1] = allspells_beg[allspells_end==-1]   
    allspells_isunidend[allspells_isunidend==-1] = allspells_isunidlim[allspells_isunidend==-1]  
    allspells_nspells[allspells_nspells==-1]=0  
    allspells_nspells=allspells_nspells+1  
       
    #Use this to construct hazards  
    spells = np.stack((allspells_beg,allspells_len,allspells_end),axis=1)   
      
    #Use this for empirical analysis  
    spells_empirical=np.stack((allspells_beg,allspells_timeb,allspells_len,allspells_end,allspells_nspells,allspells_isunid,allspells_isunidend),axis=1)  
    is_coh=((spells_empirical[:,0]==3) & (spells_empirical[:,5]==spells_empirical[:,6]))  
    spells_empirical=spells_empirical[is_coh,1:6]  
      
     
        
        
    #Now divide spells by relationship nature   
    all_spells=dict()   
    for ist,sname in enumerate(state_codes):   
   
        is_state= (spells[:,0]==ist)   
            
    
        all_spells[sname]=spells[is_state,:]   
   
        is_state= (all_spells[sname][:,1]!=0)   
        all_spells[sname]=all_spells[sname][is_state,:]   
           
           
    ############################################   
    #Construct sample of first relationships   
    ############################################   
  
       
    #Now define variables   
    rel_end = -1*np.ones((N,99),dtype=np.int16)   
    rel_age= -1*np.ones((N,99),dtype=np.int16)   
    rel_unid= -1*np.ones((N,99),dtype=np.int16)   
    rel_number= -1*np.ones((N,99),dtype=np.int16)   
    isrel = np.zeros((N,),dtype=np.int8)   
       
    for t in range(1,mdl.setup.pars['Tret']):   
           
        irchange = ((state[:,t-1] != state[:,t]) & ((state[:,t-1]==0) | (state[:,t-1]==1)))   
           
        if not np.any(irchange): continue   
       
        rel_end[irchange,isrel[irchange]]=state[irchange,t]   
        rel_age[irchange,isrel[irchange]]=t   
        rel_unid[irchange,isrel[irchange]]=changep[irchange,t]   
        rel_number[irchange,isrel[irchange]]=isrel[irchange]+1   
           
        isrel[irchange] = isrel[irchange]+1   
       
    #Get the final Variables   
    allrel_end=rel_end[(rel_end!=-1)]   
    allrel_age=rel_age[(rel_age!=-1)]   
    allrel_uni=rel_unid[(rel_unid!=-1)]   
    allrel_number=rel_number[(rel_number!=-1)]   
       
    #Get whetehr marraige   
    allrel_mar=np.zeros((allrel_end.shape))   
    allrel_mar[(allrel_end==2)]=1   
       
    #Create a Pandas Dataframe   
    data_rel=np.array(np.stack((allrel_mar,allrel_age,allrel_uni,allrel_number),axis=0).T,dtype=np.float64)   
    data_rel_panda=pd.DataFrame(data=data_rel,columns=['mar','age','uni','rnumber'])   
                      
   
       
    #Regression   
    try:   
        FE_ols = smf.ols(formula='mar ~ uni+C(rnumber)+C(age)', data = data_rel_panda.dropna()).fit()   
        beta_unid_s=FE_ols.params['uni']   
    except:   
        print('No data for unilateral divorce regression...')   
        beta_unid_s=0.0   
       
       
    moments['beta unid']=beta_unid_s    
      
    ###################################################  
    # Second regression for the length of cohabitation  
    ###################################################  
    data_coh_panda=pd.DataFrame(data=spells_empirical,columns=['age','duration','end','rel','uni'])   
      
    #Regression   
    try:   
    #FE_ols = smf.ols(formula='duration ~ uni+C(age)', data = data_coh_panda.dropna()).fit()   
    #beta_dur_s=FE_ols.params['uni']   
      
        from lifelines import CoxPHFitter  
        cph = CoxPHFitter()  
        data_coh_panda['age2']=data_coh_panda['age']**2  
        data_coh_panda['age3']=data_coh_panda['age']**3  
        data_coh_panda['rel2']=data_coh_panda['rel']**2  
        data_coh_panda['rel3']=data_coh_panda['rel']**3  
        #data_coh_panda=pd.get_dummies(data_coh_panda, columns=['age'])  
          
        #Standard Cox  
        data_coh_panda['endd']=1.0  
        data_coh_panda.loc[data_coh_panda['end']==3.0,'endd']=0.0  
        data_coh_panda1=data_coh_panda.drop(['end'], axis=1)  
        cox_join=cph.fit(data_coh_panda1, duration_col='duration', event_col='endd')  
        haz_join=cox_join.hazard_ratios_['uni']  
          
        #Cox where risk is marriage  
        data_coh_panda['endd']=0.0  
        data_coh_panda.loc[data_coh_panda['end']==2.0,'endd']=1.0  
        data_coh_panda2=data_coh_panda.drop(['end'], axis=1)  
        cox_mar=cph.fit(data_coh_panda2, duration_col='duration', event_col='endd')  
        haz_mar=cox_mar.hazard_ratios_['uni']  
          
        #Cox where risk is separatio  
        data_coh_panda['endd']=0.0  
        data_coh_panda.loc[data_coh_panda['end']==0.0,'endd']=1.0  
        data_coh_panda3=data_coh_panda.drop(['end'], axis=1)  
        cox_sep=cph.fit(data_coh_panda3, duration_col='duration', event_col='endd')  
        haz_sep=cox_sep.hazard_ratios_['uni']  
          
    except:   
        print('No data for unilateral divorce regression...')   
        haz_sep=1.0 
        haz_join=1.0 
        haz_mar=1.0 
        
    ##################################   
    # Construct the Hazard functions   
    #################################   
            
    #Hazard of Divorce   
    hazd=list()   
    lgh=len(all_spells['Couple, M'][:,0])   
    for t in range(mdl.setup.pars['T']):   
            
        cond=all_spells['Couple, M'][:,1]==t+1   
        temp=all_spells['Couple, M'][cond,2]   
        cond1=temp!=2   
        temp1=temp[cond1]   
        if lgh>0:   
            haz1=len(temp1)/lgh   
            lgh=lgh-len(temp)   
        else:   
            haz1=0.0   
        hazd=[haz1]+hazd   
            
    hazd.reverse()   
    hazd=np.array(hazd).T   
        
    #Hazard of Separation   
    hazs=list()   
    lgh=len(all_spells['Couple, C'][:,0])   
    for t in range(mdl.setup.pars['T']):   
            
        cond=all_spells['Couple, C'][:,1]==t+1   
        temp=all_spells['Couple, C'][cond,2]   
        cond1=(temp>=0) & (temp<=1)
        temp1=temp[cond1]   
        if lgh>0:   
            haz1=len(temp1)/lgh   
            lgh=lgh-len(temp)   
        else:   
            haz1=0.0   
        hazs=[haz1]+hazs   
            
    hazs.reverse()   
    hazs=np.array(hazs).T   
        
    #Hazard of Marriage (Cohabitation spells)   
    hazm=list()   
    lgh=len(all_spells['Couple, C'][:,0])   
    for t in range(mdl.setup.pars['T']):   
            
        cond=all_spells['Couple, C'][:,1]==t+1   
        temp=all_spells['Couple, C'][cond,2]   
        cond1=temp==2   
        temp1=temp[cond1]   
        if lgh>0:   
            haz1=len(temp1)/lgh   
            lgh=lgh-len(temp)   
        else:   
            haz1=0.0   
        hazm=[haz1]+hazm   
            
    hazm.reverse()   
    hazm=np.array(hazm).T   
        
    #Transform hazards pooling moments
    mdl.setup.pars['ty']=2
    if mdl.setup.pars['ty']>1:
        #Divorce
        hazdp=list()
        pop=1
        for i in range(int(mdl.setup.pars['T']/(mdl.setup.pars['ty']))):
            haz1=hazd[mdl.setup.pars['ty']*i]*pop
            haz2=hazd[mdl.setup.pars['ty']*i+1]*(pop-haz1)
            hazdp=[(haz1+haz2)/pop]+hazdp 
            pop=pop-(haz1+haz2)
        hazdp.reverse()   
        hazdp=np.array(hazdp).T 
        hazd=hazdp
            
        #Separation and Marriage
        hazsp=list()
        hazmp=list()
        pop=1
        for i in range(int(mdl.setup.pars['T']/(mdl.setup.pars['ty']))):
            hazs1=hazs[mdl.setup.pars['ty']*i]*pop
            hazm1=hazm[mdl.setup.pars['ty']*i]*pop
            
            hazs2=hazs[mdl.setup.pars['ty']*i+1]*(pop-hazs1-hazm1)
            hazm2=hazm[mdl.setup.pars['ty']*i+1]*(pop-hazs1-hazm1)
            hazsp=[(hazs1+hazs2)/pop]+hazsp
            hazmp=[(hazm1+hazm2)/pop]+hazmp
            pop=pop-(hazs1+hazs2+hazm1+hazm2)
            
        hazsp.reverse()   
        hazsp=np.array(hazsp).T 
        hazs=hazsp
        
        hazmp.reverse()   
        hazmp=np.array(hazmp).T 
        hazm=hazmp
        
    moments['hazard sep'] = hazs   
    moments['hazard div'] = hazd   
    moments['hazard mar'] = hazm   
       
   
    
        
    #Singles: Marriage vs. cohabitation transition   
    #spells_s=np.append(spells_Femalesingle,spells_Malesingle,axis=0)   
    spells_s =all_spells['Female, single']   
    cond=spells_s[:,2]>1   
    spells_sc=spells_s[cond,2]   
    condm=spells_sc==2   
    sharem=len(spells_sc[condm])/max(len(spells_sc),0.0001)   
      
      
    #Cut the first two periods give new 'length'   
    lenn=mdl.setup.pars['T']-mdl.setup.pars['Tbef']   
    assets_t=assets_t[:,mdl.setup.pars['Tbef']:mdl.setup.pars['T']]   
    iexo=iexo[:,mdl.setup.pars['Tbef']:mdl.setup.pars['T']]   
    state=state[:,mdl.setup.pars['Tbef']:mdl.setup.pars['T']]   
    theta_t=theta_t[:,mdl.setup.pars['Tbef']:mdl.setup.pars['T']]   
        
    ###########################################   
    #Moments: FLS  
    ###########################################   
        
        
    flsm=np.ones(mdl.setup.pars['Tret'])   
    flsc=np.ones(mdl.setup.pars['Tret'])   
        
        
    for t in range(mdl.setup.pars['Tret']):   
            
        pick = agents.state[:,t]==2          
        if pick.any(): flsm[t] = np.array(setup.ls_levels)[agents.ils_i[pick,t]].mean()   
        pick = agents.state[:,t]==3   
        if pick.any(): flsc[t] = np.array(setup.ls_levels)[agents.ils_i[pick,t]].mean()   
            
        
            
    moments['flsm'] = flsm   
    moments['flsc'] = flsc   
    
    ##################
    #Sample Selection#
    #################
    
    #Import the distribution from the data
    with open('freq_psid_tot.pkl', 'rb') as file:   
        freq_psid_tot_data=pickle.load(file)  
        
    #Import Get when in a couple and reshape accordingly
    resha=len(change_psid[0,:])*len(change_psid[:,0])
    state_totl=np.reshape(state_psid,resha)
    incouple= (state_totl==2) | (state_totl==3)
    incoupler=np.reshape(incouple,resha)
    
    #Define main variables
    ctemp=change_psid
    change_psid2=np.reshape(ctemp,resha)
    agetemp=np.linspace(1,len(change_psid[0,:]),len(change_psid[0,:]))
    agegridtemp=np.reshape(np.repeat(agetemp,len(change_psid[:,0])),(len(change_psid[:,0]),len(agetemp)),order='F')
    agegrid=np.reshape(agegridtemp,resha)
    
    #Keep all those guys only if the are men and in a relatioinship
    #TODO
    
    #Make data compatible with current age.
    freq_psid_tot_data['age']=freq_psid_tot_data['age']-18.0
    freq_psid_tot_data.loc[freq_psid_tot_data['age']<0.0,'age']=0.0
    
    #Drop if no change in law!
    if np.all(changep==0):
        #freq_psid_tot_data.loc[freq_psid_tot_data['age']<1910.0,'age']=1000
        freq_psid_tot_data['unid']=0
   
        
    freq_psid_tot_data2=freq_psid_tot_data.groupby(['age','unid'])['age'].count()
    
    #Create a Dataframe with simulated data to perform the draw
    inde=np.linspace(1,resha,resha,dtype=np.int32)
    
    ddd2=np.stack((inde[incoupler],agegrid[incoupler],change_psid2[incoupler]),axis=0).T
    df_psidt=pd.DataFrame(data=ddd2,columns=["Index","age","unid"],index=ddd2[:,0])
    df_psidt['age']=df_psidt['age'].astype(np.float)
    
    if len(df_psidt>0):
        sampletemp=strata_sample(["'age'", "'unid'"],freq_psid_tot_data2,frac=0.02,tsample=df_psidt,distr=True)
        final2t=df_psidt.merge(sampletemp,how='left',on='Index',indicator=True)
        
        keep3=[False]*len(df_psidt)
        keep3=(np.array(final2t['_merge'])=='both')
        
        #TODO assign labor according to stuff above
        #Keep again for all relevant variables
    
        
        #Initial distribution
        prima_psid_tot=freq_psid_tot_data2/np.sum(freq_psid_tot_data2)
        
        #Final distribution
        final3=df_psidt[keep3]
        final4=final3.groupby(['age','unid'])['age'].count()
        dopo_psid_tot=final4/np.sum(final4)
        
        
        print('The average deviation from actual to final psid_tot ditribution is {:0.2f}%'.format(np.mean(abs(prima_psid_tot-dopo_psid_tot))*100))
         
    else:
        keep3=[True]*len(df_psidt)
    ############
    #Average FLS
    ############
    
    state_totl=state_totl[incoupler][keep3]
    labor_totl=np.reshape(labor_psid,resha)
    labor_totl=labor_totl[incoupler][keep3]
    mean_fls=0.0 
    pick=((state_totl[:]==2)  | (state_totl[:]==3)) 
    if pick.any():mean_fls=np.array(setup.ls_levels)[labor_totl[pick]].mean() 
     
    moments['mean_fls'] = mean_fls 
    
    ###########################################   
    #Moments: FLS   Ratio
    ###########################################   
    
    ###################
    #Sample Selection
    ###################
    
    #Import the distribution from the data
    with open('freq_psid_par.pkl', 'rb') as file:   
        freq_psid_par_data=pickle.load(file)  
        
    #Import Get when in a couple and reshape accordingly
    resha=len(change_psid[0,:])*len(change_psid[:,0])
    state_par=np.reshape(state_psid,resha)
    incouplep= (state_par==2) | (state_par==3)
    incouplerp=np.reshape(incouplep,resha)
    
    #Define main variables
    ctemp=change_psid
    change_psid3=np.reshape(ctemp,resha)
    
    #Keep all those guys only if the are men and in a relatioinship
    #TODO
    
    #Make data compatible with current age.
    freq_psid_par_data['age']=freq_psid_par_data['age']-18.0
    freq_psid_par_data.loc[freq_psid_par_data['age']<0.0,'age']=0.0
    
    #Drop if no change in law!
    if np.all(changep==0):
        #freq_psid_par_data.loc[freq_psid_par_data['age']<1910.0,'age']=1000
        freq_psid_par_data['unid']=0
        
 
        
    freq_psid_par_data2=freq_psid_par_data.groupby(['age','unid'])['age'].count()

    
    ddd3=np.stack((inde[incouplerp],agegrid[incouplerp],change_psid3[incouplerp]),axis=0).T
   
    df_psidp=pd.DataFrame(data=ddd3,columns=["Index","age","unid"],index=ddd3[:,0])
    df_psidp['age']=df_psidp['age'].astype(np.float)
    
    if len(df_psidp>0):  
        sampletempp=strata_sample(["'age'", "'unid'"],freq_psid_par_data2,frac=0.02,tsample=df_psidt,distr=True)
        final2p=df_psidt.merge(sampletempp,how='left',on='Index',indicator=True)
        
        keep4=[False]*len(df_psidp)
        keep4=(np.array(final2p['_merge'])=='both')
        
        #TODO assign labor according to stuff above
        #Keep again for all relevant variables
    
        
        #Initial distribution
        prima_psid_par=freq_psid_par_data2/np.sum(freq_psid_par_data2)
        
        #Final distribution
        final3p=df_psidt[keep4]
        final4p=final3p.groupby(['age','unid'])['age'].count()
        dopo_psid_par=final4p/np.sum(final4p)
        
        
        print('The average deviation from actual to final psid_tot ditribution is {:0.2f}%'.format(np.mean(abs(prima_psid_par-dopo_psid_par))*100))
         
    else:
        keep4=[True]*len(df_psidp)
        
    ################
    #Ratio of fls 
    ###############
    
    state_par=state_par[incoupler][keep4]
    labor_par=np.reshape(labor_psid,resha)
    labor_par=labor_par[incouplerp][keep4]
    
    mean_fls_m=0.0 
    pick=(state_par[:]==2) 
    if pick.any():mean_fls_m=np.array(setup.ls_levels)[labor_par[pick]].mean() 
       
    mean_fls_c=0.0 
    pick=(state_par[:]==3) 
    if pick.any():mean_fls_c=np.array(setup.ls_levels)[labor_par[pick]].mean() 
     
    moments['fls_ratio']=mean_fls_m/max(mean_fls_c,0.0001) 
       
       
     
        
    ###########################################   
    #Moments: Variables over Age   
    ###########################################   
    
    #Create wages
    wage_f=np.zeros(state.shape)
    wage_m=np.zeros(state.shape)
    wage_f2=np.zeros(state_w.shape)
    wage_m2=np.zeros(state_w.shape)
    wage_fp=np.zeros(state.shape)
    wage_mp=np.zeros(state.shape)
    psis=np.zeros(state_w.shape)
    ifemale=(female[:,0]==1)
    imale=(female[:,0]==0)
    ifemale2=(female_w[:,0]==1)
    imale2=(female_w[:,0]==0)
    for i in range(len(state[0,:])):
        #Check if single women
        singlef=(ifemale) & (state[:,i]==0)
        singlem=(imale) & (state[:,i]==1)       
        nsinglef=(ifemale) & (state[:,i]>1)
        nsinglem=(imale) & (state[:,i]>1)
        
        singlef2=(ifemale2) & (state_w[:,i]==0)
        singlem2=(imale2) & (state_w[:,i]==1)       
        nsinglef2=(ifemale2) & (state_w[:,i]>1)
        nsinglem2=(imale2) & (state_w[:,i]>1)
    
        #For graphs
        wage_f[nsinglef,i]=np.exp(setup.pars['f_wage_trend'][i]+setup.exogrid.zf_t[i][((setup.all_indices(i,iexo[:,i]))[1])])[nsinglef]
        wage_m[nsinglem,i]=np.exp(setup.pars['m_wage_trend'][i]+setup.exogrid.zm_t[i][((setup.all_indices(i,iexo[:,i]))[2])])[nsinglem]
        wage_f[singlef,i]=np.exp(setup.pars['f_wage_trend'][i]+setup.exogrid.zf_t[i][iexo[singlef,i]]) 
        wage_m[singlem,i]=np.exp(setup.pars['m_wage_trend'][i]+setup.exogrid.zm_t[i][iexo[singlem,i]]) 
        wage_mp[nsinglef,i]=np.exp(setup.pars['m_wage_trend'][i]+setup.exogrid.zm_t[i][((setup.all_indices(i,iexo[:,i]))[2])])[nsinglef]
        wage_fp[nsinglem,i]=np.exp(setup.pars['f_wage_trend'][i]+setup.exogrid.zf_t[i][((setup.all_indices(i,iexo[:,i]))[1])])[nsinglem]
        psis[:,i]=((setup.exogrid.psi_t[i][(setup.all_indices(i,iexo_w[:,i]))[3]])) 
     
        #For income process validation
        wage_f2[nsinglef2,i]=np.exp(setup.pars['f_wage_trend'][i]+setup.exogrid.zf_t[i][((setup.all_indices(i,iexo_w[:,i]))[1])])[nsinglef2]
        wage_m2[nsinglem2,i]=np.exp(setup.pars['m_wage_trend'][i]+setup.exogrid.zm_t[i][((setup.all_indices(i,iexo_w[:,i]))[2])])[nsinglem2]
        wage_f2[singlef2,i]=np.exp(setup.pars['f_wage_trend'][i]+setup.exogrid.zf_t[i][iexo_w[singlef2,i]]) 
        wage_m2[singlem2,i]=np.exp(setup.pars['m_wage_trend'][i]+setup.exogrid.zm_t[i][iexo_w[singlem2,i]]) 
       
    #Update N to the new sample size   
    N=len(state)   
        
    relt=np.zeros((len(state_codes),lenn))   
    relt1=np.zeros((len(state_codes),lenn))   
    ass_rel=np.zeros((len(state_codes),lenn,2))   
    inc_rel=np.zeros((len(state_codes),lenn,2)) 
    log_inc_rel=np.zeros((2,len(state_w))) 
    
        
        
        
    #Log Income over time
    for t in range(lenn):
        ipart=(labor_w[:,t]==1) & (ifemale2)
        log_inc_rel[0,t]=np.mean(np.log(wage_f2[ipart,t]))
        log_inc_rel[1,t]=np.mean(np.log(wage_m2[imale2,t]))
        
    for ist,sname in enumerate(state_codes): 
        

        for t in range(lenn):   
                
            s=t#mdl.setup.pars['Tbef']+t    
            ftrend = mdl.setup.pars['f_wage_trend'][s]   
            mtrend = mdl.setup.pars['m_wage_trend'][s]   
                
            #Arrays for preparation   
            is_state = (np.any(state[:,0:t]==ist,1))          
            is_state1 = (state[:,t]==ist)   
            is_state2 = (state_w[:,t]==ist)   
            if t<1:   
                is_state=is_state1   
            ind = np.where(is_state)[0]   
            ind1 = np.where(is_state1)[0] 
            ind1f = np.where((is_state1) & (agents.is_female[:,0][keep][keep2]))
            ind1m = np.where((is_state1) & ~(agents.is_female[:,0][keep][keep2]))
                
            if not (np.any(is_state) or np.any(is_state1)): continue   
            
            zf,zm,psi=mdl.setup.all_indices(t,iexo[ind1,t])[1:4]   
                
            #Relationship over time   
            relt[ist,t]=np.sum(is_state)   
            relt1[ist,t]=np.sum(is_state1)   
                
            #Assets over time     
            if sname=="Female, single" or  sname=="Male, single": 
                
                ass_rel[ist,t,0]=np.mean(assets_w[is_state2,t])  
            
            else:
            
                
                ass_rel[ist,t,0]=np.mean(assets_w[(is_state2) & (ifemale2),t]) 
                ass_rel[ist,t,1]=np.mean(assets_w[(is_state2) & (imale2),t]) 
                

            
            if sname=="Female, single":  
                positive=(wage_f[ind1,t]>0)
                inc_rel[ist,t,0]=np.mean(wage_f[ind1f,t])#max(np.mean(np.log(wage_f[ind1,t])),-0.2)#np.mean(np.exp(mdl.setup.exogrid.zf_t[s][zf]  + ftrend ))  # 
                
                positive=False
            elif sname=="Male, single":  
                 positive=(wage_m[ind1,t]>0)
                 inc_rel[ist,t,0]=np.mean(wage_m[ind1m,t])#np.mean(np.exp(mdl.setup.exogrid.zf_t[s][zm] + mtrend))  #np.mean(wage_m[(state[:,t]==ist)])#
                 
                 positive=False
            elif sname=="Couple, C" or sname=="Couple, M": 
                 positive=(wage_f[ind1f,t]>0) & (wage_mp[ind1f,t]>0)
                 #inc_rel[ist,t,0]=np.mean(wage_f[ind1f,t][positive])+np.mean(wage_mp[ind1f,t][positive])#np.mean(np.exp(mdl.setup.exogrid.zf_t[s][zf] + ftrend)+np.exp(mdl.setup.exogrid.zm_t[s][zm] + mtrend))  
                 inc_rel[ist,t,0]=np.mean(wage_f[ind1f,t])+np.mean(wage_mp[ind1f,t])
                 positive=False 
                 positive=(wage_m[ind1m,t]>0) & (wage_fp[ind1m,t]>0)
                 #inc_rel[ist,t,1]=np.mean(wage_m[ind1m,t][positive])+np.mean(wage_fp[ind1m,t][positive])
                 inc_rel[ist,t,1]=np.mean(wage_m[ind1m,t])+np.mean(wage_fp[ind1m,t])
                 positive=False
            else:  
               
               print('Error: No relationship chosen')  
                 
    #Now, before saving the moments, take interval of 5 years   
    # if (mdl.setup.pars['Tret']>=mdl.setup.pars['Tret']):           
    reltt=relt[:,0:mdl.setup.pars['Tret']-mdl.setup.pars['Tbef']+1]   
    years=np.linspace(20,50,7)   
    years_model=np.linspace(20,50,30/mdl.setup.pars['py'])   
       
    #Find the right entries for creating moments   
    pos=list()   
    for j in range(len(years)):   
        pos=pos+[np.argmin(np.abs(years_model-years[j]))]   
       
    #Approximation if more than 5 years in one period   
    if len(pos)<7:   
        for i in range(7-len(pos)):   
            pos=pos+[pos[-1]]   
    pos=np.array(pos)   
       
       
       
    reltt=reltt[:,pos]   
    #else:   
     #   reltt=relt   
           
    moments['share single'] = reltt[0,:]/N   
    moments['share mar'] = reltt[2,:]/N   
    moments['share coh'] = reltt[3,:]/N   
    
    
    ###################################
    #"Event Study" with simulated data
    #################################
    
    #Build the event matrix
    age_unid_e=np.argmax(changep_w,axis=1)
    never_e=(changep_w[:,0]==0) & (age_unid_e[:]==0)
    age_unid_e[never_e]=1000
    age_unid_e[changep_w[:,-1]==0]=1000
    age_unid_e1=np.repeat(np.expand_dims(age_unid_e,axis=1),len(changep_w[0,:]),axis=1)
    
    agetemp_e=np.linspace(1,len(changep_w[0,:]),len(changep_w[0,:]))
    agegridtemp_e=np.reshape(np.repeat(agetemp_e,len(changep_w[:,0])),(len(changep_w[:,0]),len(agetemp_e)),order='F')
    age_unid_e1[agegridtemp_e<=2]=1000
    age_unid_e1[agegridtemp_e>=mdl.setup.pars['Tret']]=1000
    event=agegridtemp_e-age_unid_e1-1
    
    #Get beginning of the spell
    changem=np.zeros(state_w.shape,dtype=bool)
    changec=np.zeros(state_w.shape,dtype=bool)
    for t in range(2,mdl.setup.pars['Tret']-1):   
           
        irchangem = ((state_w[:,t]==2) & ((state_w[:,t-1]==0) | (state_w[:,t-1]==1) | (state_w[:,t-1]==3))) 
        irchangec = ((state_w[:,t]==3) & ((state_w[:,t-1]==0) | (state_w[:,t-1]==1))) 
        changem[:,t]=irchangem
        changec[:,t]=irchangec
        
    #Grid of event Studies
    eventgrid=np.array(np.linspace(-10,10,21),dtype=np.int16)
    event_thetam=np.ones(len(eventgrid))*-1000
    event_thetac=np.ones(len(eventgrid))*-1000
    event_psim=np.ones(len(eventgrid))*-1000
    event_psic=np.ones(len(eventgrid))*-1000
    i=0
    for e in eventgrid:
        
        matchm=(event==e) & (changem)
        matchc=(event==e) & (changec)
        event_thetam[i]=np.mean(theta_w[matchm])
        event_thetac[i]=np.mean(theta_w[matchc])
        event_psim[i]=np.mean(psis[matchm])
        event_psic[i]=np.mean(psis[matchc])
        i+=1
        
    if draw:   
        #Get useful package for denisty plots
        import seaborn as sns
        
        #Print something useful for debug and rest   
        print('The share of singles choosing marriage is {0:.2f}'.format(sharem))   
        cond=(state<2)   
        if assets_t[cond].size:   
            print('The max level of assets for singles is {:.2f}, the grid upper bound is {:.2f}'.format(np.amax(assets_t[cond]),max(mdl.setup.agrid_s)))   
        cond=(state>1)   
        if assets_t[cond].size:   
            print('The max level of assets for couples is {:.2f}, the grid upper bound is {:.2f}'.format(np.amax(assets_t[cond]),max(mdl.setup.agrid_c)))   
            
        #Setup a file for the graphs   
        pdf = matplotlib.backends.backend_pdf.PdfPages("moments_graphs.pdf")   
            
        #################   
        #Get data moments   
        #################   
            
        #Get Data Moments   
        with open('moments.pkl', 'rb') as file:   
            packed_data=pickle.load(file)   
            
            #Unpack Moments (see data_moments.py to check if changes)   
            #(hazm,hazs,hazd,mar,coh,fls_ratio,W)   
            hazm_d=packed_data['hazm']   
            hazs_d=packed_data['hazs']   
            hazd_d=packed_data['hazd']   
            mar_d=packed_data['emar']   
            coh_d=packed_data['ecoh']   
            fls_d=np.ones(1)*packed_data['fls_ratio']  
            mean_fls_d=np.ones(1)*packed_data['mean_fls']  
            beta_unid_d=np.ones(1)*packed_data['beta_unid']   
            hazm_i=packed_data['hazmi']   
            hazs_i=packed_data['hazsi']   
            hazd_i=packed_data['hazdi']   
            mar_i=packed_data['emari']   
            coh_i=packed_data['ecohi']   
            fls_i=np.ones(1)*packed_data['fls_ratioi']   
            mean_fls_i=np.ones(1)*packed_data['mean_flsi'] 
            beta_unid_i=np.ones(1)*packed_data['beta_unidi']   
    
            
            
        #############################################   
        # Hazard of Divorce   
        #############################################   
        fig = plt.figure()   
        f1=fig.add_subplot(2,1,1)   
        lg=min(len(hazd_d),len(hazd)) 
        if lg<2:   
            one='o'   
            two='o'   
        else:   
            one='r'   
            two='b'   
        plt.plot(np.array(range(lg))+1, hazd[0:lg],one, linestyle='--',linewidth=1.5, label='Hazard of Divorce - S')   
        plt.plot(np.array(range(lg))+1, hazd_d[0:lg],two,linewidth=1.5, label='Hazard of Divorce - D')   
        plt.fill_between(np.array(range(lg))+1, hazd_i[0,0:lg], hazd_i[1,0:lg],alpha=0.2,facecolor='b')   
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=3, fontsize='x-small')   
        plt.ylim(ymin=0)   
        #plt.legend(loc='upper left', shadow=True, fontsize='x-small')   
        plt.xlabel('Duration - Years')   
        plt.ylabel('Hazard')   
        plt.savefig('hazd.pgf', bbox_inches = 'tight',pad_inches = 0) 
            
        #############################################   
        # Hazard of Separation   
        #############################################   
        fig = plt.figure()   
        f1=fig.add_subplot(2,1,1)   
        lg=min(len(hazs_d),len(hazs)) 
        plt.plot(np.array(range(lg))+1, hazs[0:lg],one, linestyle='--',linewidth=1.5, label='Hazard of Separation - S')   
        plt.plot(np.array(range(lg))+1, hazs_d[0:lg],two,linewidth=1.5, label='Hazard of Separation - D')   
        plt.fill_between(np.array(range(lg))+1, hazs_i[0,0:lg], hazs_i[1,0:lg],alpha=0.2,facecolor='b')   
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=3, fontsize='x-small')   
        plt.ylim(ymin=0)   
        #plt.legend(loc='upper left', shadow=True, fontsize='x-small')   
        plt.xlabel('Duration - Years')   
        plt.ylabel('Hazard')   
        plt.savefig('hazs.pgf', bbox_inches = 'tight',pad_inches = 0) 
           
            
        #############################################   
        # Hazard of Marriage   
        #############################################   
        fig = plt.figure()   
        f1=fig.add_subplot(2,1,1)   
        lg=min(len(hazm_d),len(hazm)) 
   
        plt.plot(np.array(range(lg))+1, hazm[0:lg],one, linestyle='--',linewidth=1.5, label='Hazard of Marriage - S')   
        plt.plot(np.array(range(lg))+1, hazm_d[0:lg],two,linewidth=1.5, label='Hazard of Marriage - D')   
        plt.fill_between(np.array(range(lg))+1, hazm_i[0,0:lg], hazm_i[1,0:lg],alpha=0.2,facecolor='b')   
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=3, fontsize='x-small')   
        plt.ylim(ymin=0)   
        #plt.legend(loc='upper left', shadow=True, fontsize='x-small')   
        plt.xlabel('Duration - Years')   
        plt.ylabel('Hazard')   
        plt.savefig('hazm.pgf', bbox_inches = 'tight',pad_inches = 0) 
           
        ##########################################   
        # Assets Over the Live Cycle   
        ##########################################   
        fig = plt.figure()   
        f2=fig.add_subplot(2,1,1)   
            
        for ist,sname in enumerate(state_codes):   
            plt.plot(np.array(range(lenn)), ass_rel[ist,:,0],color=print(ist/len(state_codes)),markersize=6, label=sname)   
        plt.plot(np.array(range(lenn)), ass_rel[2,:,1], linestyle='--',color=print(2/len(state_codes)),markersize=6, label='Marriage male')
        plt.plot(np.array(range(lenn)), ass_rel[3,:,1], linestyle='--',color=print(3/len(state_codes)),markersize=6, label='Cohabitation other')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        #plt.legend(loc='upper left', shadow=True, fontsize='x-small')   
        plt.xlabel('Time')   
        plt.ylabel('Assets')   
            
        ##########################################   
        # Income Over the Live Cycle   
        ##########################################   
        fig = plt.figure()   
        f3=fig.add_subplot(2,1,1)   
            
        for ist,sname in enumerate(state_codes):   
              
            plt.plot(np.array(range(lenn)), inc_rel[ist,:,0],color=print(ist/len(state_codes)),markersize=6, label=sname) 
            
        plt.plot(np.array(range(lenn)), inc_rel[2,:,1], linestyle='--',color=print(2/len(state_codes)),markersize=6, label='Marriage male')
        plt.plot(np.array(range(lenn)), inc_rel[3,:,1], linestyle='--',color=print(3/len(state_codes)),markersize=6, label='Cohabitation Male')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Time')   
        plt.ylabel('Income')   
        
        ##########################################   
        # Log Income and Data
        ########################################## 
        
        #Import Data
        inc_men = pd.read_csv("income_men.csv")  
        inc_women = pd.read_csv("income_women.csv")  
        
        
        fig = plt.figure()   
        f3=fig.add_subplot(2,1,1)   
        
        lend=len(inc_men['earn_age'])
        agea=np.array(range(lend))+20
        plt.plot(agea, inc_men['earn_age'], marker='o',color=print(3/len(state_codes)),markersize=6, label='Men Data')
        plt.plot(agea, inc_women['earn_age'], marker='o',color=print(2/len(state_codes)),markersize=6, label='Women Data')
        plt.plot(agea, log_inc_rel[0,mdl.setup.pars['Tbef']:lend+mdl.setup.pars['Tbef']],color=print(2/len(state_codes)),markersize=6, label='Women Simulation')
        plt.plot(agea, log_inc_rel[1,mdl.setup.pars['Tbef']:lend+mdl.setup.pars['Tbef']],color=print(3/len(state_codes)),markersize=6, label='Men Simulation')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Age')   
        plt.ylabel('Income') 
                    
                    
        ##########################################   
        # Relationship Over the Live Cycle   
        ##########################################         
        fig = plt.figure()   
        f4=fig.add_subplot(2,1,1)   
        xa=(mdl.setup.pars['py']*np.array(range(len(relt1[0,])))+20)  
        for ist,sname in enumerate(state_codes):   
            plt.plot([],[],color=print(ist/len(state_codes)), label=sname)   
        plt.stackplot(xa,relt1[0,]/N,relt1[1,]/N,relt1[2,]/N,relt1[3,]/N,   
                      colors = ['b','y','g','r'])              
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Age')   
        plt.ylabel('Share')   
            
        ##########################################   
        # Relationship and Data   
        ##########################################         
        fig = plt.figure()   
        f4=fig.add_subplot(2,1,1)   
        lg=min(len(mar_d),len(relt[1,:]))   
        xa=(5*np.array(range(lg))+20)  
        plt.plot(xa, mar_d[0:lg],'g',linewidth=1.5, label='Married - D')   
        plt.fill_between(xa, mar_i[0,0:lg], mar_i[1,0:lg],alpha=0.2,facecolor='g')   
        plt.plot(xa, reltt[2,0:lg]/N,'g',linestyle='--',linewidth=1.5, label='Married - S')   
        plt.plot(xa, coh_d[0:lg],'r',linewidth=1.5, label='Cohabiting - D')   
        plt.fill_between(xa, coh_i[0,0:lg], coh_i[1,0:lg],alpha=0.2,facecolor='r')   
        plt.plot(xa, reltt[3,0:lg]/N,'r',linestyle='--',linewidth=1.5, label='Cohabiting - S')   
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.ylim(ymax=1.0)   
        plt.xlabel('Age')   
        plt.ylabel('Share')   
        plt.margins(0,0) 
        plt.savefig('erel.pgf', bbox_inches = 'tight',pad_inches = 0) 
            
        ##########################################   
        # FLS Over the Live Cycle   
        ##########################################         
        fig = plt.figure()   
        f5=fig.add_subplot(2,1,1)   
        xa=(mdl.setup.pars['py']*np.array(range(mdl.setup.pars['Tret']))+20)  
        plt.plot(xa, flsm,color='r', label='Marriage')   
        plt.plot(xa, flsc,color='k', label='Cohabitation')            
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Age')   
        plt.ylabel('FLS')   
        
        ##########################################   
        # Distribution of Love 
        ##########################################  
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)
        
        
        sns.kdeplot(psis[state_w==3], shade=True, color="r", bw=.05,label = 'Cohabitaition')
        sns.kdeplot(psis[state_w==2], shade=True, color="b", bw=.05,label = 'Marriage')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Love Shock')   
        plt.ylabel('Denisty') 
        
        ##########################################   
        # Distribution of Pareto Weight 
        ##########################################  
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)
        
        
        sns.kdeplot(theta_w[state_w==3], shade=True, color="r", bw=.05,label = 'Cohabitaition')
        sns.kdeplot(theta_w[state_w==2], shade=True, color="b", bw=.05,label = 'Marriage')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Female Pareto Weight')   
        plt.ylabel('Denisty') 
        
        ##########################################   
        # Event Study Love Shock
        ##########################################  
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)
        
        plt.plot(eventgrid, event_psic,color='r', label='Cohabitation')
        plt.plot(eventgrid, event_psim,color='b', label='Marriage')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Time Event')   
        plt.ylabel('Love Shock') 
        
        ##########################################   
        # Event Study Pareto Weight
        ##########################################  
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)
        
        plt.plot(eventgrid, event_thetac,color='r', label='Cohabitation')
        plt.plot(eventgrid, event_thetam,color='b', label='Marriage')
        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.3),   
                  fancybox=True, shadow=True, ncol=len(state_codes), fontsize='x-small')   
        plt.xlabel('Time Event')   
        plt.ylabel('Female Pareto weight') 
  
        ##########################################   
        # DID of unilateral fivorce on part choice   
        ##########################################   
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)   
            
           
        # create plot   
        x=np.array([0.25,0.75])  
        y=np.array([beta_unid_d,beta_unid_s])   
        yerr=np.array([(beta_unid_i[1]-beta_unid_i[0])/2.0,0.0])   
        plt.axhline(linewidth=0.1, color='r')   
        plt.errorbar(x, y, yerr=yerr, fmt='o', elinewidth=0.03)   
        plt.ylabel('OLS Coefficient - UniD')   
        plt.xticks(x, ["Data","Simulation"] )  
        plt.ylim(ymax=0.1)   
        plt.xlim(xmax=1.0,xmin=0.0)   
         
        ##########################################   
        # FLS: Marriage vs. cohabitation 
        ##########################################    
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)   
            
           
        # create plot   
        x=np.array([0.25,0.75])  
        y=np.array([fls_d,mean_fls_m/max(mean_fls_c,0.0001)])   
        yerr=np.array([(fls_i[1]-fls_i[0])/2.0,0.0])   
        plt.axhline(y=1.0,linewidth=0.1, color='r')   
        plt.errorbar(x, y, yerr=yerr, fmt='o', elinewidth=0.03)   
        plt.ylabel('Ratio of Female Hrs: Mar/Coh')   
        plt.xticks(x, ["Data","Simulation"] )  
        #plt.ylim(ymax=0.1)   
        plt.xlim(xmax=1.0,xmin=0.0)   
         
         
        ##########################################   
        # FLS 
        ##########################################     
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)   
            
           
        # create plot   
        x=np.array([0.25,0.75])  
        y=np.array([mean_fls_d,mean_fls])   
        yerr=np.array([(mean_fls_i[1]-mean_fls_i[0])/2.0,0.0])   
        plt.errorbar(x, y, yerr=yerr, fmt='o', elinewidth=0.03)   
        plt.ylabel('Female Labor Hours')   
        plt.xticks(x, ["Data","Simulation"] )  
        #plt.ylim(ymax=0.1)   
        plt.xlim(xmax=1.0,xmin=0.0)   
         
           
          
        ##########################################################  
        # Histogram of Unilateral Divorce on Cohabitation Length  
        #############################################################  
        fig = plt.figure()   
        f6=fig.add_subplot(2,1,1)   
            
           
        # create plot   
        x=np.array([0.2,0.5,0.8])  
        y=np.array([haz_join,haz_mar,haz_sep])   
        yerr=y*0.0   
        plt.axhline(y=1.0,linewidth=0.1, color='r')   
        plt.errorbar(x, y, yerr=yerr, fmt='o', elinewidth=0.03)   
        plt.ylabel('Relative Hazard - UniD vs. Bil')   
        plt.xticks(x, ["Overall Risk","Risk of Marriage","Risk of Separation"] )  
        #plt.ylim(ymax=1.2,ymin=0.7)   
        plt.xlim(xmax=1.0,xmin=0.0)   
        #plt.xticks(index , ('Unilateral', 'Bilateral'))   
         
    
        ##########################################   
        # Put graphs together   
        ##########################################   
        #show()   
        for fig in range(1, plt.gcf().number + 1): ## will open an empty extra figure :(   
            pdf.savefig( fig )   
           
        pdf.close()   
        matplotlib.pyplot.close("all")   
        
          
    return moments  
            
           
