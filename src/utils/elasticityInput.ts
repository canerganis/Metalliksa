export const SYMMETRY_FIELDS: Record<string, string[]> = {
  cubic: ['c11', 'c12', 'c44'],
  hexagonal: ['c11', 'c33', 'c12', 'c13', 'c44'],
  trigonal: ['c11', 'c33', 'c12', 'c13', 'c14', 'c44'],
  tetragonal: ['c11', 'c33', 'c12', 'c13', 'c44', 'c66'],
  orthorhombic: ['c11', 'c22', 'c33', 'c12', 'c13', 'c23', 'c44', 'c55', 'c66'],
  isotropic: ['c11', 'c12']
};

export type InputMode = 'custom' | 'isotropic';
export type CrystalSystem = 'cubic' | 'hexagonal' | 'trigonal' | 'tetragonal' | 'orthorhombic' | 'isotropic';

export interface ElasticityFormState {
  input_mode: InputMode;
  crystal_system: CrystalSystem;
  cij: Record<string, string>;
  k_vrh: string;
  g_vrh: string;
  density: string;
  formula: string;
  molar_mass: string;
  atoms_per_formula_unit: string;
}

export function buildElasticityInput(form: ElasticityFormState): any {
  const result: any = {
    input_mode: form.input_mode
  };

  if (form.formula.trim() !== '') {
    result.formula = form.formula.trim();
  } else {
    // Some backend signatures might require formula as string, but prompt says formula is optional.
    // If backend requires it we might need to send something, but we'll strictly omit it if empty as requested.
  }

  if (form.density.trim() !== '') {
    const density = Number(form.density);
    if (!Number.isFinite(density) || density <= 0) {
      throw new Error("Density must be a positive number.");
    }
    result.density = density;
  }

  const mmStr = form.molar_mass.trim();
  const atomsStr = form.atoms_per_formula_unit.trim();
  if (mmStr !== '' || atomsStr !== '') {
    if (mmStr === '' || atomsStr === '') {
      throw new Error("Molar mass and atoms per formula unit must be provided together.");
    }
    const mm = Number(mmStr);
    const atoms = Number(atomsStr);
    if (!Number.isFinite(mm) || mm <= 0) {
      throw new Error("Molar mass must be a positive number.");
    }
    if (!Number.isFinite(atoms) || atoms <= 0) {
      throw new Error("Atoms per formula unit must be a positive number.");
    }
    result.molar_mass = mm;
    result.atoms_per_formula_unit = atoms;
  }

  if (form.input_mode === 'isotropic') {
    const k = Number(form.k_vrh);
    const g = Number(form.g_vrh);
    if (!Number.isFinite(k) || k <= 0) {
      throw new Error("Isotropic K must be a positive number.");
    }
    if (!Number.isFinite(g) || g <= 0) {
      throw new Error("Isotropic G must be a positive number.");
    }
    result.k_vrh = k;
    result.g_vrh = g;
    result.crystal_system = 'isotropic';
  } else {
    result.crystal_system = form.crystal_system;
    {
      const requiredFields = SYMMETRY_FIELDS[form.crystal_system];
      if (!requiredFields) {
        throw new Error(`Unknown crystal system: ${form.crystal_system}`);
      }

      const custom_c_ij: Record<string, number> = {};
      for (const field of requiredFields) {
        const valStr = form.cij[field];
        if (valStr === undefined || valStr.trim() === '') {
          throw new Error(`Missing required stiffness component ${field}.`);
        }
        const val = Number(valStr);
        if (!Number.isFinite(val)) {
          throw new Error(`Stiffness component ${field} must be a finite number.`);
        }

        // Diagonal must be positive, off-diagonal can be negative but must be finite
        const isDiagonal = field[1] === field[2]; // e.g. 'c11', 'c22', 'c33', 'c44', 'c55', 'c66'
        if (isDiagonal && val <= 0) {
          throw new Error(`Diagonal stiffness component ${field} must be positive.`);
        }

        custom_c_ij[field] = val;
      }
      result.custom_c_ij = custom_c_ij;
    }
  }

  return result;
}
