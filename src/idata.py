#! -*- coding: utf-8 -*-

##    Description    Flame Idata class
##
##    Authors:       Manuel Pastor (manuel.pastor@upf.edu)
##
##    Copyright 2018 Manuel Pastor
##
##    This file is part of Flame
##
##    Flame is free software: you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation version 3.
##
##    Flame is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License
##    along with Flame. If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import hashlib

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem import Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors
from rdkit.Chem import AllChem

import multiprocessing as mp

import sdfileutils as sdfu
from standardiser import standardise

class Idata:

    def __init__ (self, control, ifile):

        self.control = control      # control object defining the processing
        self.ifile = ifile          # input file

    def extractAnotations (self, ifile):
        """         
        Extracts molecule names, biological anotations and experimental values from an SDFile . 
        Returns a tupple with three lists:
            - Molecule names
            - Molecule activity values
            - Molecule activity type (i.e. IC50)        
        """

        suppl = Chem.SDMolSupplier(ifile)
        obj_nam = []
        obj_bio = []
        obj_exp = []

        for i, mol in enumerate(suppl):

            # Do not even try to process molecules not recognised by RDKit. 
            # They will be removed at the normalization step
            if mol is None:
                continue
                
            name = sdfu.getName(mol, count=i, field=self.control.SDFile_name, suppl= suppl)

            activity_num = None
            exp = None

            if mol.HasProp(self.control.SDFile_activity):
                activity_str = mol.GetProp(self.control.SDFile_activity)
                try:
                    activity_num = float (activity_str)
                except:
                    activity_num = None            

            if mol.HasProp(self.control.SDFile_experimental):
                exp = mol.GetProp(self.control.SDFile_experimental)

            obj_nam.append(name)
            obj_bio.append(activity_num)
            obj_exp.append(exp)

        result = (obj_nam, obj_bio, obj_exp)

        return result

    def normalize (self, ifile, clean=False):
        """
        Generates a simplified SDFile with MolBlock and an internal ID for further processing

        Also, when defined in control, applies chemical standardization protocols, like the 
        one provided by Francis Atkinson (EBI), accessible from:

            https://github.com/flatkinson/standardiser
        
        Returns a tuple containing the result of the method and (if True) the name of the 
        output molecule and an error message otherwyse

        WARNING: if clean is set to True it will remove the original file
        """

        try:
            suppl=Chem.SDMolSupplier(ifile)
        except:
            success = False
            result = 'Error at processing input file for standardizing structures'
        else:
            success = True
            filename, fileext = os.path.splitext(ifile)
            ofile = filename + '_std' + fileext
            with open (ofile,'w') as fo:
                mcount = 0
                merror = 0
                for m in suppl:

                    # molecule not recognised by RDKit
                    if m is None:
                        print ("ERROR: unable to process molecule #"+str(merror))
                        merror+=1
                        continue

                    # if standardize
                    if self.control.chemstand_method == 'standardize':
                        try:
                            parent = standardise.run (Chem.MolToMolBlock(m))
                        except standardise.StandardiseException as e:
                            if e.name == "no_non_salt":
                                parent = Chem.MolToMolBlock(m)
                            else:
                                return False, e.name
                        except:
                            return False, "Unknown standardiser error"

                    # in any case, write parent plus internal ID (flameID)
                    fo.write(parent)

                    flameID = 'fl%0.10d' % mcount
                    fo.write('>  <flameID>\n'+flameID+'\n\n')

                    mcount += 1

                    # terminator
                    fo.write('$$$$\n')

            if clean:
                try:
                    os.remove (ifile)
                except OSError:
                    pass

            result = ofile

        return success, result

    def ionize (self, ifile):
        """ Adjust the ionization status of the molecular strcuture, using a given pH.
        """

        return True, ifile

    def _convert3D_ETKDG(self, ifile):
        """ Assigns 3D structures to the molecular structures provided as input.
        """
        try:
            suppl=Chem.SDMolSupplier(ifile)
        except:
            return False, 'unable to compute 3D structures'
        
        filename, fileext = os.path.splitext(ifile)
        ofile = filename + '_3d' + fileext
        with open (ofile,'w') as fo:
            for mol in suppl:
                mol3=Chem.AddHs(mol)
                AllChem.EmbedMolecule(mol3, AllChem.ETKDG())

                fo.write (Chem.MolToMolBlock(mol3))
                fo.write('\n$$$$\n')

        return True, ofile

    def convert3D (self, ifile):
        """ Assigns 3D structures to the molecular structures provided as input.
        """
        success = False
        results = 'not converted to 3D'

        if 'ETKDG' in self.control.convert3D_method :
            success, results  = self._convert3D_ETKDG(ifile)
            
        return success, results

    def computeMD_custom (self, ifile):

        # empty template, only for overriding by internal methods
        
        return False, 'not implemented'

    # TODO: move to another module all "_computeMD" methods
    def _computeMD_RDKit_properties (self, ifile):
        try:
            suppl=Chem.SDMolSupplier(ifile)
        except:
            return False, 'unable to compute RDKit properties'
 
        properties = rdMolDescriptors.Properties()

        md_nam = []
        
        for nam in properties.GetPropertyNames():
            md_nam.append(nam)

        print (len(md_nam), md_nam)

        xmatrix = np.zeros ((len(suppl),len(md_nam)),dtype=np.float64)

        for i,mol in enumerate(suppl):      
            xmatrix [i] = properties.ComputeProperties(mol)

        return True, xmatrix

    def _computeMD_RDKit_md (self, ifile):
        try:
            suppl=Chem.SDMolSupplier(ifile)
        except:
            return False, 'unable to compute RDKit MD'
 
        nms=[x[0] for x in Descriptors._descList]

        md = MoleculeDescriptors.MolecularDescriptorCalculator(nms)

        print(len(nms), nms)

        xmatrix = np.zeros ((len(suppl),len(nms)),dtype=np.float64)

        for i,mol in enumerate(suppl):      
            xmatrix [i] = md.CalcDescriptors(mol) 

        return True, xmatrix
    

    def computeMD (self, ifile):
        """ Uses the molecular structures for computing an array of values (int or float) 
        """

        # any call to computeMD_[whatever] must return a numpy array with a value for
        # each molecule in ifile       
        
        results_all = []

        if 'RDKit_properties' in self.control.MD :
            success, results  = self._computeMD_RDKit_properties(ifile)
            if success :
                results_all.append(results)
        
        if 'RDKit_md' in self.control.MD :
            success, results  = self._computeMD_RDKit_md(ifile)
            if success :
                results_all.append(results)
        
        if 'custom' in self.control.MD :
            success, results  = self.computeMD_custom(ifile)
            if success :
                results_all.append(results)
        
        if len(results_all) == 0:
            success = False
            results = 'undefined MD'

        # TODO: consolidate all results checking that the number of objects is the same for all the pieces
        #for r in results:
            

        return success, results

    def consolidate (self, results, nobj):
        """ Mix the results obtained by multiple CPUs into a single result file 
        """

        success = True
        first = True
        nresults = None

        for iresults in results:
            if iresults[0] == False :
                success = False
                break
            
            if type (iresults[1]).__module__ == np.__name__:

                if first:
                    nresults = iresults [1]
                    first = False
                else:
                    nresults = np.vstack ((nresults, iresults[1]))

                print ('merge arrays')
            
            else :
                print ('unknown')

        if success:
            result = nresults
        else:
            result = 'Error in consolidation'

        return True, result

    def save (self, results):
        """ 
        Saves the results in serialized form, together with the MD5 stamp of the control class
        """

        print (self.control.md5stamp())
        # pickle results + stamp in ifile.pickle
        # return True

        return True

    def workflow (self, ifile):
        """         
        Executes in sequence methods required to generate MD, starting from a single molecular file

        input : ifile, a molecular file in SDFile format
        output: results is a numpy bidimensional array containing MD       
        """

        # tfile is the name of the temporary molecular file and will change in the workflow
        tfile = ifile  

        # normalize chemical  
        success, results = self.normalize (tfile)
        if not success:
            results = 'Input error: chemical standardization failed: '+str(results)
        else:
            tfile = results

        #print ('normalize: '+tfile+' '+str(sdfu.count_mols(tfile)))

        # ionize molecules
        if self.control.ionize_method != None:
            success, results = self.ionize (tfile)
            if not success:
                return False, "input error: molecule ionization error at position: "+str(results)
            else:
                tfile = results

        # generate a 3D structure
        if self.control.convert3D_method != None:
            success, results = self.convert3D (tfile)
            if not success:
                return False, "input error: 3D conversion error at position: "+str(results)
            else:
                tfile = results

        # compute MD
        success, results = self.computeMD (tfile)
        if not success:
            return False, "input error: failed computing MD: "+str(results)

        return success, results

    def run (self, verbose_error=True):
        """         
        Process input file to obtain metadata (size, type, number of objects, name of objects, etc.) as well
        as for generating MD
            
        The results are saved in a MD5 stamped pickle, to avoid recomputing model input from the same input
        file
        
        This methods supports multiprocessing, splitting original files in a chunck per CPU        
        """

        # TODO: check for presence of pickle file
        # if true, extract MD5 stamp, compute control MD5 stamp and if both are coincident extract results and exit
        
        # processing for molecular input (for now an SDFile)
        if (self.control.input_type == 'molecule'):

            # trick to avoid RDKit dumping warnings to the console
            if not verbose_error:
                stderr_fileno = sys.stderr.fileno()       # saves current syserr
                stderr_save = os.dup(stderr_fileno)
                stderr_fd = open('errorRDKit.log', 'w')   # open a specific RDKit log file
                os.dup2(stderr_fd.fileno(), stderr_fileno)

            # extract useful information from file

            results = self.extractAnotations (self.ifile)
            self.obj_nam = results[0]
            self.obj_bio = results[1]
            self.obj_exp = results[2]

            # print (self.obj_nam)
            # print (self.obj_bio)
            # print (self.obj_exp)

            # Execute the workflow in 1 or n CPUs
            if self.control.numCPUs > 1:
                # Count number of molecules and split in chuncks 
                # for multiprocessing 
                success, results = sdfu.split_SDFile(self.ifile, self.control.numCPUs)

                if not success : 
                    return False, "error splitting: "+self.ifile

                split_files_names = results[0]
                split_files_sizes = results[1]

                print (split_files_names, split_files_sizes)

                pool = mp.Pool(self.control.numCPUs)
                results = pool.map(self.workflow, split_files_names)

                # Check the results and make sure there are 
                # no missing objects.
                # Reassemble results for parallel computing results
                success, results = self.consolidate(results, split_files_sizes) 
            else:
                success, results = self.workflow (self.ifile)

            if not verbose_error:
                stderr_fd.close()                     # close the RDKit log
                os.dup2(stderr_save, stderr_fileno)   # restore old syserr

        # processing for non-molecular input
        elif (self.control.input_type == 'data'):

            #   test and obtain dimensions
            #   normalize data

            print ("data")

        else:

            print ("unknown input format")

        # save and stamp
        success = self.save (results)

        # results is a tuple with:
        # [0] X numpy
        # [1] Y numpy
        # [2] flameID       this is important for retrieving structure
        # [2] objnames      for presenting results
        # [3] expinfo       for prediction quality assessment      

        return success, (results, self.obj_bio, None, self.obj_nam, self.obj_exp)
