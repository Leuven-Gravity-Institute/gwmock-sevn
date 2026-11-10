//
// Created by Giuliano Iorio on 15/10/24.
//

#include <wdformation.h>


void WDFormation::Register(WDFormation *ptr) {
    //Register only if the name is not already in the map,
    //this is necessary to avoid multiple registration of the same model when the constructor is called from
    //inherited classes
    if (GetStaticMap().find(ptr->name())==GetStaticMap().end()){
            GetStaticMap().insert(std::make_pair(ptr->name(), ptr));
            GetUsed().resize(GetStaticMap().size());
            GetUsed()[GetUsed().size() - 1] = 0;
    }
}

/**
 * Just raise a sevnerror error if the star is a nullptr
 */
WDFormation::WDFormation(Star *s, _UNUSED utilities::MassContainer *preWDmass) {
    if (s==nullptr){
        SevnLogging svlog;
        svlog.critical("WDformation cannot be initialised with an empty pointer",
                       __FILE__,__LINE__,sevnstd::sevnerr(""));
    }
}


WDFormation *WDFormation::Instance(const std::string &name, Star *s, utilities::MassContainer *preWDmass) {



    auto it = GetStaticMap().find(name);


    //If the name is in the list update the counter
    if (it != GetStaticMap().end()){
        GetUsed()[std::distance(GetStaticMap().begin(), it)] = 1;
    }
        //otherwise return an error
    else{
        SevnLogging svlog;
        std::string available_options;
        for (auto const& option : GetStaticMap()) available_options+=option.first+", ";
        svlog.critical("Option "+name+" not available for Process WD formation. The available options are: \n"+available_options,
                       __FILE__,__LINE__,sevnstd::notimplemented_error(" "));
    }


    return (it->second)->instance(s,preWDmass); //when I call the instance create a new object with the non trivial constructor
}


