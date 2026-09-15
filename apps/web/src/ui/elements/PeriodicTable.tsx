import type { ElementSummary } from '../../api/types';

/**
 * Presentation-level grid placement for the periodic table.
 *
 * The underlying periodic facts (symbol, number, period, group, block) all
 * come from the backend/ChemEngine. This layout only decides where a cell
 * sits on screen. The engine reports `group: 3` for the whole f-block, so
 * the lanthanides (58–71) and actinides (90–103) are placed in the two
 * conventional f-block rows below the main table; La and Ac remain in the
 * main table at group 3 as the dataset specifies.
 */
export function gridPosition(el: ElementSummary): {
  row: number;
  col: number;
} {
  if (el.atomic_number >= 58 && el.atomic_number <= 71) {
    return { row: 9, col: 4 + (el.atomic_number - 58) };
  }
  if (el.atomic_number >= 90 && el.atomic_number <= 103) {
    return { row: 10, col: 4 + (el.atomic_number - 90) };
  }
  return { row: el.period, col: el.group };
}

export interface PeriodicTableProps {
  elements: ElementSummary[];
  selectedSymbol: string | null;
  onSelect: (element: ElementSummary) => void;
}

/**
 * The interactive periodic table. Each cell is a real button (mouse,
 * keyboard, and touch all work), labelled for screen readers as
 * "Name, atomic number N".
 */
export function PeriodicTable({ elements, selectedSymbol, onSelect }: PeriodicTableProps) {
  return (
    <div className="ptable-scroll" role="group" aria-label="Periodic table">
      <div className="ptable" data-testid="periodic-table">
        {elements.map((el) => {
          const { row, col } = gridPosition(el);
          const selected = el.symbol === selectedSymbol;
          return (
            <button
              key={el.atomic_number}
              type="button"
              className={`ptable-cell block-${el.block}${selected ? ' selected' : ''}`}
              style={{ gridRow: row, gridColumn: col }}
              aria-pressed={selected}
              aria-label={`${el.name}, atomic number ${el.atomic_number}`}
              data-testid={`element-${el.symbol}`}
              onClick={() => onSelect(el)}
            >
              <span className="ptable-z">{el.atomic_number}</span>
              <span className="ptable-symbol">{el.symbol}</span>
            </button>
          );
        })}
      </div>
      <p className="help muted ptable-legend">
        s-block · p-block · d-block · f-block — select an element to explore its
        electron structure.
      </p>
    </div>
  );
}
