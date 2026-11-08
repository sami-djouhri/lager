import { Link } from 'react-router-dom';
import { useBereich, weg } from './kontext';

/** Seitenkopf in einem Bereich: der Bereich als Etikett ueber dem Titel,
    damit auf jeder Seite steht, in welchem Teil des Lagers man ist. */
export default function Kopf({ titel }: { titel: string }) {
  const { schluessel, bereich } = useBereich();
  return (
    <>
      <Link to={weg(schluessel)} className="page-bereich">
        {bereich?.name ?? ''}
      </Link>
      <h1 className="page-title">{titel}</h1>
    </>
  );
}
