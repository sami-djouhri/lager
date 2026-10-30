import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import type { ProductOut, Page } from '../types';

interface Props {
  onSelect: (product: ProductOut) => void;
  placeholder?: string;
}

export default function ProductSelect({ onSelect, placeholder = 'Produkt suchen...' }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<ProductOut[]>([]);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (query.length < 1) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const data = await api.get<Page<ProductOut>>(`/products?q=${encodeURIComponent(query)}`);
        setResults(data.items);
        setOpen(true);
        setHighlighted(-1);
      } catch {
        setResults([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function handleSelect(product: ProductOut) {
    setQuery(product.name);
    setOpen(false);
    onSelect(product);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!open || results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlighted((h) => (h + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlighted((h) => (h - 1 + results.length) % results.length);
    } else if (e.key === 'Enter' && highlighted >= 0) {
      e.preventDefault();
      handleSelect(results[highlighted]);
    }
  }

  return (
    <div className="autocomplete" ref={wrapperRef}>
      <input
        type="text"
        className="form-input"
        placeholder={placeholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onKeyDown={handleKeyDown}
      />
      {open && results.length > 0 && (
        <div className="autocomplete-list">
          {results.map((p, i) => (
            <div
              key={p.id}
              className={`autocomplete-item${i === highlighted ? ' highlighted' : ''}`}
              onClick={() => handleSelect(p)}
            >
              <div>{p.name}</div>
              {p.category && <div className="autocomplete-item-sub">{p.category}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
