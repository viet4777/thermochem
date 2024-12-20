# -*- coding: utf-8 -*-
"""
This module extracts the information provided in *Third Millennium Ideal Gas
and Condensed Phase Thermochemical Database for Combustion with Updates from
Active Thermochemical Tables* by A. Burcat and B. Ruscic. It needs the actual
database BURCAT_THR.xml to run, which is already included in the thermochem
library.
"""

from __future__ import division
from __future__ import print_function
import os
try:
    from xml.etree.ElementTree import parse
except ImportError:
    from elementtree import parse
import numpy as np

# Universal gas constant R
R = 8.314472


class Element(object):
    """
    This is a helper class.  It is intended to be created via an
    Elementdb object but it can be used on its own. Take a look at
    Elementdb class for example usage.

    Units are in standard units: K, J, kg. Conversion functions are provided in
    the external units module.

    One extra feature not explained in Elementdb documentation is that
    it contains the number of each atom, useful for computing chemical
    reactions.

    >>> db = Elementdb()
    >>> weird = db.getelementdata("C8H6O2")
    >>> print(weird.elements)
    [('C', 8), ('H', 6), ('O', 2)]
    """

    def __init__(self, formula, Tmin_, _Tmax, mm, hfr, elements):
        self.formula = formula
        self.Tmin_ = Tmin_
        self._Tmax = _Tmax
        self.mm = mm
        self.hfr = hfr
        self.elements = elements

    def density(self, p, T):
        """
        Density in kg/m³.
        """
        return p * self.mm / R / T

    def cpo(self, T):
        """
        Calculates the specific heat capacity in J/mol K
        """
        # I know perfectly that the most efficient way of evaluating
        # polynomials is recursively but I want the implementation to
        # be as explicit as possible
        # TODO: Setting array element with sequence will be deprecated in Numpy
        Ta = np.array([1, T, T ** 2, T ** 3, T ** 4], 'd')
        if T > 200 and T <= 1000:
            return np.dot(self.Tmin_[:5], Ta) * R
        elif T > 1000 and T < 6000:
            return np.dot(self._Tmax[:5], Ta) * R
        else:
            raise ValueError("Temperature out of range")

    def cp_(self, T):
        """
        Computes the specific heat capacity in J/kg K for a given temperature
        """
        return self.cpo(T) / self.mm

    @property
    def cp(self):
        """
        Computes the specific heat capacity in J/kg K at 298 K (Reference T)
        """
        return self.cp_(298)

    def ho(self, T):
        """
        Computes the sensible enthalpy in J/mol
        """
        Ta = np.array([1, T / 2, T ** 2 / 3, T ** 3 / 4, T ** 4 / 5, 1 / T], 'd')
        if T > 200 and T <= 1000:
            return np.dot(self.Tmin_[:6], Ta) * R * T
        elif T > 1000 and T < 6000:
            return np.dot(self._Tmax[:6], Ta) * R * T
        else:
            raise ValueError("Temperature out of range")

    def h(self, T):
        """
        Computes the total enthalpy in J/kg
        """
        return self.cp_(T) * T

    def so(self, T):
        """
        Computes entropy in J/mol K
        """
        Ta = np.array([np.log(T), T, T ** 2 / 2, T ** 3 / 3, T ** 4 / 4, 0, 1], 'd')
        if T > 200 and T <= 1000:
            return np.dot(self.Tmin_, Ta) * R
        elif T > 1000 and T < 6000:
            return np.dot(self._Tmax, Ta) * R
        else:
            raise ValueError("Temperature out of range")

    def go(self, T):
        """
        Computes the Gibbs free energy from the sensible enthalpy in
        J/mol
        """
        if T > 200 and T < 6000:
            return self.ho(T) - self.so(T) * T
        else:
            raise ValueError("Temperature out of range")

    def __repr__(self):
        return """<element> %s""" % (self.formula)

    def __str__(self):
        return """<element> %s""" % (self.formula)

    def __unicode__(self):
        return u"""<element> %s""" % (self.formula)


class Mixture(object):
    """
    Class that models a gas mixture. Currently, only volume (molar)
    compositions are supported.

    You can iterate through all its elements. The item returned is a tuple
    containing the element and the amount.

    >>> db = Elementdb()
    >>> mix = db.getmixturedata([("O2 REF ELEMENT", 20.9476),\
    ("N2  REF ELEMENT", 78.084),\
    ("CO2", 0.0319),\
    ("AR REF ELEMENT", 0.9365),\
    ])
    >>> mix_list = [(e[0], round(e[1], 6)) for e in mix]
    >>> for e in mix_list: print(e)
    (<element> O2 REF ELEMENT, 20.9476)
    (<element> N2  REF ELEMENT, 78.084)
    (<element> CO2, 0.0319)
    (<element> AR REF ELEMENT, 0.9365)

    You can get elements either by index or by value.

    >>> print(mix['CO2'])
    (<element> CO2, 0.0319)

    You can also delete components of a mixture. Needed by the MoistAir class

    >>> mix.delete('CO2')
    >>> print(mix)
    <Mixture>:
        O2 REF ELEMENT at 20.9476
        N2  REF ELEMENT at 78.084
        AR REF ELEMENT at 0.9365
    """

    def __init__(self, config='vol'):
        self.mix = list()
        self.config = config
        self.idx = 0

    # The following functions are an iterator. Its purpose is to be able to
    # iterate through all the elements of a mix.
    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def next(self):
        try:
            rv = self.mix[self.idx]
            self.idx += 1
            return rv

        except:
            self.idx = 0
            raise StopIteration

    def __getitem__(self, i):
        if isinstance(i, int):
            return self.mix[i]

        if isinstance(i, str):
            elem = (None, None)
            for e in self.mix:
                if i == e[0].formula:
                    elem = e

            return elem

    def add(self, component, prop):
        """Add a component to the mixture"""
        self.mix.append((component, prop))

    def delete(self, formula):
        """Delete a formula from the mixture"""
        erased = False
        for e in self.mix:
            if e[0].formula == formula:
                self.mix.remove(e)
                erased = True

        if not erased:
            raise ValueError("Not a component")

    @property
    def mm(self):
        """
        Computes the equivalent molar mass for a mix

        .. math::

          M_m = \\frac{1}{N_m} \\sum_i N_i M_i
        """
        if self.config == 'vol':
            Nm = 0
            Mm = 0
            for comp in self.mix:
                Nm += comp[1]

            for comp in self.mix:
                Mm += comp[1] * comp[0].mm

            return Mm / Nm

    def density(self, p, T):
        """
        Computes the density for a given mix of gases in kg/m³

        The equivalent R for a mix is :math:`R_m = \\frac{R_u}{M_n}`,
        where :math:`M_n` is the equivalent molar mass for the mix.
        """
        return p * self.mm / R / T

    def extensive(self, attr, T):
        """
        Computes the extensive value for a mix. Remember that an extensive
        value depends on the amount of matter. Enthalpy and volume are
        extensive values.

        .. math::

          ext = \\frac{1}{N_m M_m} \\sum_i N_i M_i ext_i
        """
        if self.config == 'vol':
            Nm = 0
            Mm = 0
            ext = 0
            for comp in self.mix:
                Nm += comp[1]

            for comp in self.mix:
                Mm += comp[1] * comp[0].mm

            Mm = Mm / Nm

            for comp in self.mix:
                # Tricky use of getattr function to avoid cutting and
                # pasting several times the very same code
                iattr = getattr(comp[0], attr)
                ext += comp[1] * comp[0].mm * iattr(T)

            return ext / Nm / Mm

    def cp_(self, T):
        """
        Computes the heat capacity at a given temperature in J/kg K.
        """
        return self.extensive('cp_', T)

    @property
    def cp(self):
        """
        Computes the heat capacity at room temperature, 298.15K.
        Results in J/kg K.
        """
        return self.extensive('cp_', 298.15)

    def ho(self, T):
        """
        Estimate the sensible enthalpy of the mixture in J/mol.
        """
        return self.extensive('ho', T)

    def h(self, T):
        """
        Estimate the total enthalpy of the mixture in J/kg.
        """
        return self.cp_(T) * T

    def so(self, T):
        """
        Estimate the entropy of the mixture in J/mol K.
        """
        return self.extensive('so', T)

    def go(self, T):
        """
        Estimate the Gibbs free energy using the sensible enthalpy of the
        mixture in J/mol.
        """
        return self.extensive('go', T)

    def __repr__(self):
        repr_str = "<Mixture>:"
        for comp in self.mix:
            repr_str += "\n    %s at %s" % (comp[0].formula, comp[1])
        return repr_str

    def __str__(self):
        return self.__repr__()

    def __unicode__(self):
        repr_str = u"<Mixture>:"
        for comp in self.mix:
            repr_str += u"\n    %s at %s" % (comp[0].formula, comp[1])

        return repr_str


class Elementdb(object):
    """
    Class that reads the Alexander Burcat's thermochemical database
    for combustion.

    >>> db = Elementdb()
    >>> oxygen = db.getelementdata("O2 REF ELEMENT")
    >>> print(oxygen)
    <element> O2 REF ELEMENT
    >>> print('molar mass', oxygen.mm)
    molar mass 0.0319988
    >>> print('heat capacity', round(oxygen.cp, 6))
    heat capacity 918.078952

    The reference temperature for enthalpy is 298.15 K

    >>> print('entropy', round(oxygen.so(298), 6))
    entropy 205.133746
    >>> print('gibbs free energy', round(oxygen.go(298), 6))
    gibbs free energy -61134.262901

    There's a search function. It is very useful because some names
    are a bit tricky. Well, not this one.

    >>> db.search("AIR")
    ['AIR']
    >>> air = db.getelementdata("AIR")
    >>> print('air molar mass', air.mm)
    air molar mass 0.02896518
    >>> print('heat capacity', round(air.cp, 6))
    heat capacity 1004.776251
    >>> print(round(air.density(101325, 298), 6))
    1.184519

    The element database can create also mixtures.  It returns an
    instance of Mixture object that can give you the same as the
    Element class for any mixture.

    >>> mix = db.getmixturedata([("O2 REF ELEMENT", 20.9476),\
    ("N2  REF ELEMENT", 78.084),\
    ("CO2", 0.0319),\
    ("AR REF ELEMENT", 0.9365),\
    ])
    >>> print(mix)
    <Mixture>:
        O2 REF ELEMENT at 20.9476
        N2  REF ELEMENT at 78.084
        CO2 at 0.0319
        AR REF ELEMENT at 0.9365
    >>> print(round(mix.cp, 6))
    1004.722171
    >>> print(round(mix.mm, 6))
    0.028965
    """

    def __init__(self):
        """
        The database file is read when the class is instantiated.
        This is terribly slow as the database is more than 2MB.
        Create the instance and the elements at boot, otherwise be
        prepared to face huge computation times.
        """
        dirname = os.path.dirname(__file__)
        burcat = os.path.join(dirname, 'BURCAT_THR.xml')
        with open(burcat, 'r') as database:
            tree = parse(database)
        self.db = tree.getroot()

    def search(self, formula):
        """
        List all the species containing a string. Helpful for
        interactive use of the database.
        """
        matches = []
        for specie in self.db:
            try:
                for element in specie:
                    try:
                        if element.tag == "phase":
                            if formula in element.find("formula").text:
                                matches.append(element.find("formula").text)
                    except:
                        pass
            except:
                pass

        return matches

    def getelementdata(self, formula):
        """
        Returns an element instance given the name of the element.
        """
        Tmin_ = np.zeros(7)
        _Tmax = np.zeros(7)
        comp = []

        def element_matches(element, formula):
            """Check if element matches a formula"""
            phase_element = element.tag == "phase"
            return phase_element and element.find("formula").text == formula

        for specie in self.db:
            for element in specie:
                if element_matches(element, formula):
                    phase = element
                    coefficients = phase.find("coefficients")
                    low = coefficients.find("range_Tmin_to_1000")
                    for i, c in zip(range(7), low):
                        Tmin_[i] = float(c.text)

                    high = coefficients.find("range_1000_to_Tmax")
                    for i, c in zip(range(7), high):
                        _Tmax[i] = float(c.text)

                    elements = phase.find("elements")
                    for elem in elements:
                        elem_data = elem.attrib
                        comp.append((elem_data['name'], int(elem_data['num_of_atoms'])))

                    mm = float(phase.find("molecular_weight").text) / 1000
                    hfr = float(coefficients.find("hf298_div_r").text)

                    return Element(formula, Tmin_, _Tmax, mm, hfr, comp)

    def getmixturedata(self, components):
        """
        Creates a mixture of components given a list of tuples
        containing the formula and the volume percent
        """
        mixture = Mixture()
        for comp in components:
            mixture.add(self.getelementdata(comp[0]), comp[1])

        return mixture
