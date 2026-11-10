//
// Created by Giuliano Iorio on 15/10/24.
//

#ifndef SEVN_HURLEYHE_H
#define SEVN_HURLEYHE_H

#include <wdformation.h>

class WDHurleyHE : virtual  public  WDFormation{

public:
    /**Standard constructor it just register**/
    WDHurleyHE() : WDFormation()  {Register(this);};

    /**
     * Main constructor. During the construction the WD_mass and WD_type are set
     * @param s poinnter to a Star that is turning into a WD
     * @param preWDmass A mass container (see utilities) contanining the total mass, mhe mass and mco mass
     * at the moment of the WD formation. It is optional and if it is presents it contains the final properties
     * of the star just before the WD formation. They can be different than the current stellar properties, for example
     * because the tracks are not advanced enough to reach the full envelope stripping. If they are present,
     * they should be used instead of the mass from the object star.
     */
    explicit WDHurleyHE(_UNUSED Star* s, _UNUSED utilities::MassContainer* preWDmass= nullptr);

    /**Name of the WD formation model, this will be use at runtime to select the  given model**/
    inline std::string name() const override {return "wdhurleyhe";}

    static WDHurleyHE _wdhurleyhe; //Static instance to initialise and register the object

    /**
    * Create an instance of the class allocated on the heap
    * @return a pointer to a real instance of the class that is allocated on the  heap
    */
    WDHurleyHE *instance(Star* s, _UNUSED utilities::MassContainer* preWDmass) override{
        return (new WDHurleyHE(s,preWDmass));
    };

};


#endif //SEVN_HURLEYHE_H
