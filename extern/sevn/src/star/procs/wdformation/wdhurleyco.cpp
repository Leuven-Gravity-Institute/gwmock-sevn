//
// Created by Giuliano Iorio on 15/10/24.
//

#include <wdhurleyco.h>
#include <star.h>

WDHurleyCO::WDHurleyCO(_UNUSED Star* s, _UNUSED utilities::MassContainer* preWDmass) : WDFormation(s,preWDmass) {

    double preWDMCO{0.}, preWDMHE{0.};
    if (preWDmass != nullptr){
        preWDMCO = preWDmass->MCO;
        preWDMHE = preWDmass->MHE;
    } else{
        preWDMCO = s->getp(MCO::ID);
        preWDMHE = s->getp(MHE::ID);
    }

    //GI: 26/04/2023
    //TODO: Is this the best implementation we can have? It is true that a stripped low mass star never ignite Helium?
    //Following Hurley, a HeWD is formed when a low-mass star (a star with MZAMS<MHEf, mass helium flash) loses the envelope when it is
    //has not yet started the core Helium burning (see setting kw = 10 in hrdiag.f).
    //So here we just assume that a HeWD is formed if the stars arrive at this point with a MCO=0. ATM, it is not really possible
    //to arrive here through normal SSE with MCO=0, but this method can be triggered externally by some event in binary.
    //This is what we actually implemented in the method used to transform the star in a pureHe (Star::jump_to_pureHE_tracks), if it has not a CO core yet and Mzams< approx 2,
    //the turn_into_remnant method is called and we enter in the first condition forming a HeWD.
    if (preWDMCO<=utilities::TINY){
        set_WD_mass(preWDMHE); //WD mass taken as the mass of the HE core
        set_WD_type(Lookup::Remnants::HeWD);
    }
    else {
        set_WD_mass(preWDMCO); //WD mass taken as the mass of the CO core
        // GI: 08/05/2026
        // We follow the same criterion as Hurley+00 (Section 6,
        // https://academic.oup.com/mnras/article/315/3/543/972062):
        // the classification into COWD or ONeWD is based on the helium core mass
        // at the base of the AGB (M_{c,BAGB}). If M_{c,BAGB} < 1.6 Msun the
        // remnant is a COWD, otherwise an ONeWD.
        //
        // We identify the base of the AGB with the start of the Shell He Burning
        // (SHeBurning) phase. To retrieve M_{c,BAGB}, we initialise an auxiliary
        // star with the same ZAMS mass, metallicity, and star type (H-star or
        // He-star) at the beginning of this phase, and read off the helium core
        // mass. This is analogous to Hurley+00, where M_{c,BAGB} (like all core
        // mass relations) depends on the initial mass M0, which in our framework
        // corresponds to the ZAMS mass of the interpolating track. Track jumps
        // are therefore automatically accounted for.
        Star s_auxiliary(s, 0, s->get_zams(), s->get_Z(), "hesb", s->amifollowingpureHetrack());
        double Mc_AGB = s_auxiliary.getp(MHE::ID);
        if (Mc_AGB < 1.6)
            set_WD_type(Lookup::Remnants::COWD);
        else
            set_WD_type(Lookup::Remnants::ONeWD);
    }

}



