"""Shopping list + Forecast + Meal-Plan routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain import DomainError
from app.schemas import (
    ForecastItemOut,
    MealPlanRequest,
    MealPlanResponse,
    RecipeOut,
    ShoppingSuggestionOut,
)
from app.services import meal_plan as meal_plan_service
from app.services.shopping import ShoppingService, forecast as forecast_service

router = APIRouter(tags=["shopping"])


@router.get("/api/shopping-list", response_model=list[ShoppingSuggestionOut])
def shopping_list(
    analysis_days: int = Query(30, ge=1, le=365),
    expiring_within_days: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db),
):
    svc = ShoppingService(db)
    return svc.suggestions(
        analysis_days=analysis_days,
        expiring_within_days=expiring_within_days,
    )


@router.get("/api/forecast", response_model=list[ForecastItemOut])
def forecast(
    days: int = Query(14, ge=1, le=365),
    kind: str = Query("expire", pattern="^(expire|run_out)$"),
    db: Session = Depends(get_db),
):
    return forecast_service(db, days=days, kind=kind)


@router.get("/api/recipes", response_model=list[RecipeOut])
def list_recipes():
    return [
        RecipeOut(
            id=r.id,
            name=r.name,
            servings_default=r.servings_default,
            ingredients=r.ingredients,
        )
        for r in meal_plan_service.list_recipes()
    ]


@router.post("/api/meal-plan", response_model=MealPlanResponse)
def meal_plan(body: MealPlanRequest, db: Session = Depends(get_db)):
    try:
        return meal_plan_service.plan(
            db,
            recipe_ids=body.recipe_ids,
            servings=body.servings,
        )
    except meal_plan_service.RecipeNotFoundError as exc:
        raise DomainError("Rezept nicht gefunden", {"recipe_id": str(exc)}) from exc
