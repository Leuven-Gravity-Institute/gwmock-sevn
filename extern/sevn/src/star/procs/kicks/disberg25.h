/*
Created by Giuliano Iorio on 09/12/25.
It includes kick models from the Disberg&Mandel25 paper: https://ui.adsabs.harvard.edu/abs/2025ApJ...989L...8D/abstract
*/

#ifndef SEVN_DISBERG25_H
#define SEVN_DISBERG25_H


#include <kicks.h>


/**
 * SN kick following the Disber&Mandel25 (https://ui.adsabs.harvard.edu/abs/2025ApJ...989L...8D/abstract)
 * kick distribution for NS following a lognormal distribution. THe parameters of the lognormal can be set
 * at runtime with parameters sn_kick_velocity_mean_disberg (default 5.60 following Disberg&Mandel25) and
 * sn_kick_velocity_stdev_disberg (default 0.68 following Disberg&Mandel25).
 */
class DisbergPure : public Kicks{
    DisbergPure(bool reg = true){
        if(reg) {
            Register(this, name());
        }
    }

    static DisbergPure _disbergpure;

    void _apply(Star *s) override;

    //when I use the regist function I use the non trivial constructor of the Hermite6th class
    DisbergPure* instance() {
        return (new DisbergPure(false));
    }

    inline std::string name() override { return "disberg_pure"; }
};

/**
 * Same as DisbergPure, but the kicks are corrected for the SN fallback (larger fallback, lower velocities)
 */
class Disberg : virtual public Kicks{

public:
    Disberg(bool reg = true){
        if(reg) {
            Register(this, name());
        }
    }

    static Disberg _disberg;

    void _apply(Star *s) override;

    //when I use the regist function I use the non trivial constructor of the Hermite6th class
    Disberg* instance() {
        return (new Disberg(false));
    }

    inline std::string name() override { return "disberg"; }

protected:

    /**
     * Estimate the fallback f_b to correct the kick, i.e.
     * Vk_new = Vk_old *f_b, where f_b = (1-fallback)
     * The fallback is introduced in the rapid and delayed SN model as
     *
     * fallback = (Mremnant - Mproto) / (MpreSN - Mproto)
     *
     * where Mproto depends on the SN model, in SEVN Mproto = 1.1 for rapid and 1.15 for delayed
     *
     * However, the Sn model can set the fallback, therefore in this method we firstly check if the
     * fallback in the SN model is set (i.e. >=0), in this case we use the value set by the SN model
     * otherwise we use the equation above assuming Mproto=1.1 Msun.
     *
     * @param s Pointer to the exploding star
     * @return the fallback correction term fb
     */
     double estimate_fallback_correction(Star *s);

};

/**
 * Kicks from Giacobbo & Mapelli 2020, https://ui.adsabs.harvard.edu/abs/2020ApJ...891..141G/abstract
 * Natal kicks are drawn from the Disberpure, but then they are rescaled by a factor proportional to Mejecta/Mremnant.
 * Vkick propto Mejecta takes into accoun the SN asymmetries, while Vkick propto 1/MBH takes into account the
 * conservation of linear momentum
 */
class DisbergUnified : public Kicks{

    DisbergUnified(bool reg = true){
        if(reg) {
            Register(this, name());
        }
    }

    static DisbergUnified _disbergunified;

    void _apply(Star *s) override;

    DisbergUnified* instance() {
        return (new DisbergUnified(false));
    }

    inline std::string name() override { return "disberg_unified"; }

};


#endif //SEVN_DISBERG25_H
