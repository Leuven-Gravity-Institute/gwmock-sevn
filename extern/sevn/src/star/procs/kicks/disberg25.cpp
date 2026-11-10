//
// Created by Giuliano Iorio on 09/12/25.
//
#include <disberg25.h>
#include <star.h>
#include <supernova.h>

/********* Disberg25 Pure **************/

void DisbergPure::_apply(Star *s) {

    double disberg_std = s -> get_svpar_num("sn_kick_velocity_stdev_disberg");
    double disberg_mean = s -> get_svpar_num("sn_kick_velocity_mean_disberg");

    //lognormal distribution for velocities with mean=5.6 and sigma=0.68 as in Disberg & Mandel 2025, APJL 989 L8
    double kickTEMP = draw_from_lognormal(disberg_std, disberg_mean);
    double costheta = draw_from_uniform(-1.0, 1.0);
    double thetaTEMP = std::acos(costheta);   
    double phiTEMP = draw_from_uniform(0.0,2*M_PI);
    
    s->vkick[0] = kickTEMP * std::sin(thetaTEMP) * std::sin(phiTEMP);    
    s->vkick[1] = kickTEMP * std::sin(thetaTEMP) * std::cos(phiTEMP);    
    s->vkick[2] = kickTEMP * std::cos(thetaTEMP);    
    s->vkick[3] = random_velocity_kick = kickTEMP;
}


/********* Disberg25  **************/

void Disberg::_apply(Star *s) {

    double disberg_std = s -> get_svpar_num("sn_kick_velocity_stdev_disberg");
    double disberg_mean = s -> get_svpar_num("sn_kick_velocity_mean_disberg");

    //lognormal distribution for velocities with mean=5.6 and sigma=0.68 as in Disberg & Mandel 2025, APJL 989 L8
    //all kicks are rescaled accordingly to the fallback fraction (direct collapse = no kicks)
    double kickTEMP = draw_from_lognormal(disberg_std, disberg_mean);
    double costheta = draw_from_uniform(-1.0, 1.0);
    double thetaTEMP = std::acos(costheta);   
    double phiTEMP = draw_from_uniform(0.0,2*M_PI);
    
    s->vkick[0] = kickTEMP * std::sin(thetaTEMP) * std::sin(phiTEMP);    
    s->vkick[1] = kickTEMP * std::sin(thetaTEMP) * std::cos(phiTEMP);    
    s->vkick[2] = kickTEMP * std::cos(thetaTEMP);    
    s->vkick[3] = random_velocity_kick = kickTEMP;

    //TODO This kick model is based on the fallback fraction that is properly defined only
    //in the rapid and delayed model. So either we disable this kick model for the others sn model
    //or we can use the approximate method below to estimate the fallback frack
    double f_fb_correction = estimate_fallback_correction(s);

    for (auto& vkick : s->vkick)
        vkick*=f_fb_correction;


}

double Disberg::estimate_fallback_correction(Star *s) {

    double f_fb_correction;

    /** New proptotype for fb estimate ***/
    //Atm if the SN model do not se the fallback frac is it is equal to -1, below there is a simple solution
    //to estimate the fallback frack assuming always a proto compact object mass of 1.1 Msun.
    //Correct new
    if (s->get_supernova()->get_fallback_frac()<0){
        //NOTICE: in the classical Rapid and Delayed formalism, the fallback is estimated
        //considering the compact remnant mass before the correction for the neutrino mass loss
        //and pair instability, therefore here we emulate this formalism considering the Mass of the remnant
        //not corrected.
        const double& Mrem   = s->get_supernova()->get_Mremnant_preCorrection();
        const double& MpreSN = s->get_supernova()->get_preSN_Mass(Mass::ID);
        const double Mproto  = 1.1;

        double fb = std::max((Mrem - Mproto),0.) / std::max(MpreSN - Mproto,Mproto);
        f_fb_correction = 1 - fb;
    }  else{
        f_fb_correction = (1.0 - s->get_supernova()->get_fallback_frac());
    }


    /*** Old implementation ***/
    //f_fb_correction =  s->get_supernova()->get_fallback_frac() != -1 ? (1.0 - s->get_supernova()->get_fallback_frac()) : 1.0;


    if (f_fb_correction>1 or f_fb_correction<0){
        svlog.critical("Fallback correction ("+utilities::n2s(f_fb_correction,__FILE__,__LINE__)+
                       ") is outside the range [0,1]",__FILE__,__LINE__,sevnstd::sanity_error(""));
    }

    return  f_fb_correction;

}


void DisbergUnified::_apply(Star *s) {

    double disberg_std = s -> get_svpar_num("sn_kick_velocity_stdev_disberg");
    double disberg_mean = s -> get_svpar_num("sn_kick_velocity_mean_disberg");

    ///Initial check
    if (s->get_supernova()->get_AverageEjected()<0)
        svlog.critical("Average Ejected Mass in Unified kick is negative. It is likely not initialised  in your chosen SN model ("
                       +s->get_supernova()->name()+").",__FILE__,__LINE__,sevnstd::sn_error());
    else if (s->get_supernova()->get_AverageRemnant()<0)
        svlog.critical("Average remnant Mass in Unified kick is negative. It is likely not initialised  in your chosen SN model ("
                       +s->get_supernova()->name()+").",__FILE__,__LINE__,sevnstd::sn_error());

    // double unified_std = s -> get_svpar_num("sn_kick_velocity_stdev");

    // Neutrino mass loss is included in s->get_supernova()->get_Mejected() = M_star_final - Mremnant, i.e.  s->get_supernova()->get_Mejected() is ALWAYS != 0.
    // Note: for ECSNe, Mejected = MCO - Mremnant, i.e. kicks are != 0 because of neutrino mass loss (in principle, kicks != 0 should come from the ejection of tiny envelopes around ONe-WD)

    double ejected_mass = s->get_supernova()->get_fallback_frac() == 1 ? 0.0 : (s->get_supernova()->get_remnant_type() == Lookup::Remnants::NS_ECSN ? std::max(s->getp(MCO::ID) - s->get_supernova()->get_Mremnant(),0.0) : s->get_supernova()->get_Mejected()); //do not consider neutrinos in case of direct collapse
    double correction = (ejected_mass/s->get_supernova()->get_AverageEjected()) * (s->get_supernova()->get_AverageRemnant()/s->get_supernova()->get_Mremnant());

    //Sanity check in the correction factor
    if (correction<0){
        svlog.critical("SN kicks correction factor for the unified model is negative: "+utilities::n2s(correction,__FILE__,__LINE__)+
                       ". This has been estimated with the following properties:"+
                       "\n fallback: "+utilities::n2s(s->get_supernova()->get_fallback_frac(),__FILE__,__LINE__)+
                       "\n Remnant type: "+utilities::n2s(s->get_supernova()->get_remnant_type(),__FILE__,__LINE__)+
                       "\n Mremnant: "+utilities::n2s(s->get_supernova()->get_Mremnant(),__FILE__,__LINE__) +
                       "\n MCO: "+utilities::n2s(s->getp(MCO::ID),__FILE__,__LINE__) +
                       "\n Mejecta: "+utilities::n2s(s->get_supernova()->get_Mejected(),__FILE__,__LINE__)+
                       "\n Finale ejected mass: "+utilities::n2s(ejected_mass,__FILE__,__LINE__)+
                       "\n Mejecta average: "+utilities::n2s(s->get_supernova()->get_AverageEjected(),__FILE__,__LINE__)+
                       "\n Mremnant average: "+utilities::n2s(s->get_supernova()->get_AverageRemnant(),__FILE__,__LINE__),
                       __FILE__,__LINE__, sevnstd::sanity_error(" "));

    }

    double kickTEMP = draw_from_lognormal(disberg_std, disberg_mean);
    double costheta = draw_from_uniform(-1.0, 1.0);
    double thetaTEMP = std::acos(costheta);   
    double phiTEMP = draw_from_uniform(0.0,2*M_PI);
    
    s->vkick[0] = kickTEMP * std::sin(thetaTEMP) * std::sin(phiTEMP);    
    s->vkick[1] = kickTEMP * std::sin(thetaTEMP) * std::cos(phiTEMP);    
    s->vkick[2] = kickTEMP * std::cos(thetaTEMP); 
    s->vkick[3] = kickTEMP;
    //Velocity kick before correction
    random_velocity_kick = s->vkick[3];
    //Correct
    for (auto& vkick : s->vkick){
        vkick*=correction;
    }
}
