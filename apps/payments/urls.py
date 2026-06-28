from django.urls import path
from . import views

urlpatterns = [
    path('wallet/', views.WalletView.as_view(), name='wallet'),
    path('wallet/transactions/', views.WalletTransactionListView.as_view(), name='wallet-transactions'),
    path('commissions/', views.CommissionListView.as_view(), name='commissions'),
    path('operational-logs/', views.OperationalLogListCreateView.as_view(), name='operational-log-list-create'),
    path('operational-logs/<int:pk>/', views.OperationalLogDeleteView.as_view(), name='operational-log-delete'),
    path('wallet/topup/', views.wallet_topup, name='wallet-topup'),
    path('budget-suggestion/', views.BudgetSuggestionView.as_view(), name='budget-suggestion'),
    path('budget-suggestion/dismiss/', views.dismiss_budget, name='dismiss-budget'),
    path('generate-code/', views.generate_topup_code, name='generate-topup-code'),
    path('redeem-code/', views.redeem_topup_code, name='redeem-topup-code'),
]
