// Type-Shim: leitet alle Schemas an die generierte OpenAPI-Source-of-Truth weiter.
// Source: src/types.generated.ts (generiert via `npm run gen:types`).
//
// Bestehende Importe `import type { ProductOut } from '../types'` bleiben funktional;
// die tatsächlichen Type-Definitionen kommen aus dem FastAPI-Schema.
import type { components } from './types.generated';

type Schemas = components['schemas'];

export type NutritionInfo = Schemas['NutritionInfo'];
export type ProductOut = Schemas['ProductOut'];
export type ProductCreate = Schemas['ProductCreate'];
export type ProductUpdate = Schemas['ProductUpdate'];
export type StockEntryOut = Schemas['StockEntryOut'];
export type StockEntryCreate = Schemas['StockEntryCreate'];
export type ConsumeRequest = Schemas['ConsumeRequest'];
export type ConsumptionEventOut = Schemas['ConsumptionEventOut'];
export type AvailabilityOut = Schemas['AvailabilityOut'];
export type ExpiryForecastItem = Schemas['ExpiryForecastItem'];
export type ConsumptionByProduct = Schemas['ConsumptionByProduct'];
export type WasteSummary = Schemas['WasteSummary'];
export type TurnoverResult = Schemas['TurnoverResult'];
export type CategoryAnalyticsItem = Schemas['CategoryAnalyticsItem'];
export type LowStockItem = Schemas['LowStockItem'];

// OpenAPI generiert pro Page[T]-Endpoint eine eigene konkrete Variante
// (Page_ProductOut_, Page_StockEntryOut_, ...). Wir behalten zusätzlich
// dieses Generic, weil es typsicher mit jedem T arbeitet und in Konsumenten
// ergonomischer liest als der lange generierte Name.
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export type ElectronicAssetOut = Schemas['ElectronicAssetOut'];
export type PortfolioOut = Schemas['PortfolioOut'];
export type MarketValueUpdateOut = Schemas['MarketValueUpdateOut'];
export type ShoppingSuggestionOut = Schemas['ShoppingSuggestionOut'];
export type ForecastItemOut = Schemas['ForecastItemOut'];
export type RecipeOut = Schemas['RecipeOut'];
export type MealPlanRequest = Schemas['MealPlanRequest'];
export type MealPlanResponse = Schemas['MealPlanResponse'];
export type MealPlanShoppingItem = Schemas['MealPlanShoppingItem'];
export type MealPlanMissingProduct = Schemas['MealPlanMissingProduct'];

// BarcodeResult ist im Backend kein Pydantic-Schema (dynamisches dict im barcode-Endpoint),
// daher hier explizit als Frontend-Modell: bleibt manuell in Sync mit app/api/routes_barcode.py.
export interface BarcodeResult {
  source: 'db' | 'openfoodfacts' | null;
  product: {
    barcode: string;
    name: string;
    category?: string | null;
    nutrition_per_100?: NutritionInfo | null;
    image_url?: string | null;
    default_unit?: string;
    typical_pack_sizes?: number[];
    shelf_life_days_default?: number | null;
  } | null;
}
