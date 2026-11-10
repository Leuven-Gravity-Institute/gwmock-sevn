/*
Created by Giuliano Iorio on 15/10/24.
Module for WD formation models, it includes:
 - Class WDFormation: Base class for WD models
*/
#ifndef SEVN_WDFORMATION_H
#define SEVN_WDFORMATION_H

#include <string>
#include <vector>
#include <map>
#include <sevnlog.h>
#include <utilities.h>
#include <lookup_and_phases.h>

#define _UNUSED __attribute__ ((unused))

class Star;
using sevnstd::SevnLogging;

class WDFormation {

public:
    /**Standard constructor it just register**/
    WDFormation(){Register(this);};
    /**
     * Main constructor. During the construction the WD_mass and WD_type are set
     * @param s poinnter to a Star that is turning into a WD
     * @param preWDmass A mass container (see utilities) contanining the total mass, mhe mass and mco mass
     * at the moment of the WD formation. It is optional and if it is presents it contains the final properties
     * of the star just before the WD formation. They can be different than the current stellar properties, for example
     * because the tracks are not advanced enough to reach the full envelope stripping. If they are present,
     * they should be used instead of the mass from the object star.
     * NOTE: If for any reason the WD formation ends with no remnant, you must use:
     *      set_WD_mass(0.);
     *      set_WD_type(Lookup::Remnants::Empty);
     */
    explicit WDFormation(_UNUSED Star* s, _UNUSED utilities::MassContainer* preWDmass= nullptr);
    virtual ~WDFormation() = default;
    /** Get a proper instance, based on the name or return a not implemented error if not available**/
    static WDFormation *Instance(std::string const &name, Star *s, utilities::MassContainer* preWDmass= nullptr);

    /**Name of the WD formation model, this will be use at runtime to select the  given model**/
    virtual inline std::string name() const {return "wdformation";}

    /** Get the WD mass **/
    double get_WDmass() const {return _WD_mass;}
    /** Get the WD type, it will one of the element in the Lookup::Remnants enum  **/
    Lookup::Remnants get_WDtype() const {return _WD_type;}

    /**
     * Create an instance of the class allocated on the heap
     * @return a pointer to a real instance of the class that is allocated on the  heap
     */
    virtual WDFormation *instance(Star* s, _UNUSED utilities::MassContainer* preWDmass) = 0;

protected:

    void Register(WDFormation *ptr);


    double _WD_mass{0.};
    Lookup::Remnants _WD_type{Lookup::Remnants::NotARemnant};

    inline void set_WD_mass(double WD_mass){_WD_mass=WD_mass;}
    inline void set_WD_type(Lookup::Remnants WD_type){_WD_type=WD_type;}

private:

    static std::map<std::string, WDFormation *> &GetStaticMap() {
        static std::map<std::string, WDFormation *> _locmap;
        return _locmap;
    }

    static std::vector<int> &GetUsed() {
        static std::vector<int> _used;
        return _used;
    }

};

#endif //SEVN_WDFORMATION_H
