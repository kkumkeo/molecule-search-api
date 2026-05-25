from rdkit import Chem


def substructure_search(molecules, substructure):
    sub_mol = Chem.MolFromSmiles(substructure)

    if sub_mol is None:
        raise ValueError("Incorrect substructure SMILES")

    result = []

    for smiles in molecules:
        mol = Chem.MolFromSmiles(smiles)

        if mol is None:
            continue

        if mol.HasSubstructMatch(sub_mol):
            result.append(smiles)

    return result