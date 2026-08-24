from django.urls import path
from . import views, views_rfq, views_req, views_po
from procurement.procureapp.master_procurement import master_procurement_plan as master

urlpatterns = [
    path('', views.dashboard, name='procurement'),
    path('plans/master/', master, name='master_procurement_plan'),

    # suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/register/', views.supplier_register, name='supplier_register'),
    path('suppliers/<int:pk>/<str:phone>/update/', views.update_supplier, name='update_supplier'),
    path('suppliers/<int:pk>/activate/', views.activate_supplier, name='activate_supplier'),
    path('suppliers/<int:pk>/<str:phone>/<str:title>/delete/', views.trash_supplier, name='trash_supplier'),

    # procurements
    path('procurements/', views.ProcurementPlanListView.as_view(), name='requisition_list'),
    path('procurements/create/', views.procurement_create, name='requisition_create'),
    path('procurements/<int:pk>/', views.ProcurementPlanDetailView.as_view(), name='requisition_detail'),
    path('approve/procurement/<int:pk>/review/', views.review_procurement, name='requisition_review'),
    path('approve/procurement/<int:pk>/approve/', views.approve_procurement, name='requisition_approve'),
    path('procurement/<int:pk>/delete/<slug:slug>/', views.trash_procurement, name='trash_requisition'),
    path('procurement/<int:pk>/item/update/', views.procurement_update,
         name='procurement_update'),
    path('get-product-cost/', views.get_product_cost, name='get_product_cost'),

    path('RFQ/<str:reference_no>/email/', views_rfq.send_rfq_to_supplier, name='send_rfq_to_supplier'),
    path('plans/<int:pk>/rfq/', views_rfq.create_rfq, name='plan_rfq'),
    path('rfq/list', views_rfq.rfq_list, name='rfq_list'),
    path('rfq/<slug:slug>/<str:reference_no>/detail/', views_rfq.rfq_detail, name='rfq_detail'),
    path('rfq/<int:pk>/<slug:slug>/trash/', views_rfq.trash_rfq, name='trash_rfq'),
    path('rfq/<str:reference_no>/log_rfq/', views_rfq.log_rfq, name='log_rfq'),

    # reqs
    path('req/', views_req.RequisitionListView.as_view(), name='req_list'),
    path('approve/req/<int:pk>/approve/', views_req.req_approve, name='req_approve'),
    path('req/create/', views_req.req_create, name='req_create'),

    path('req/<int:pk>/', views_req.RequisitionDetailView.as_view(), name='po_detail'),
    path('req/<int:pk>/update/', views_req.req_update, name='po_update'),
    path('req/<int:pk>/delete/<slug:slug>/', views_req.trash_req, name='trash_po'),

    path('product/create/', views.create_product, name='create_product'),
    path('product/<int:pk>/<str:name>/del/', views.trash_product, name='trash_pro'),
    path('product/<str:name>/<int:pk>/update/', views.update_product, name='edit_pro'),
    path('product/list/', views.ProductListView.as_view(), name='product_list'),

    # Reports
    path('reports/spent/', views.spent_report, name='spent_report'),
    path('reports/supplier/', views.supplier_report, name='supplier_report'),
    path('supplier-spend-report/purchase-order/<int:pk>/detail/', views.supplier_spend_report_detail, name='supplier_spend_report_detail'),
    path('supplier-spend-report/<int:pk>/update/', views.supplier_spend_report_update, name='supplier_spend_report_update'),
    path('reports/supplier/<int:supplier_id>/', views.supplier_report, name='supplier_detail_report'),

    # Lpo
    path('send_log/<int:send_log_id>/create-po/', views_po.create_purchase_order, name='create_purchase_order'),
    path('po/<slug:slug>/cancel/', views_po.po_cancel, name='po_cancel'),
    path('purchase_order/<int:pk>/', views_po.purchase_order_detail, name='purchase_order_detail'),
    path('purchase_/order/list/', views_po.purchase_order_list, name='purchase_order'),
]
