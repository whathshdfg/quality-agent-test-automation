# 接口文档

## 创建订单接口
POST /api/order/create

请求参数：
- user_id
- start_location
- end_location

返回字段：
- code
- message
- order_id

## 取消订单接口
POST /api/order/cancel

请求参数：
- user_id
- order_id
- cancel_reason

返回字段：
- code
- message
- order_status

## 支付接口
POST /api/payment/pay

请求参数：
- user_id
- order_id
- amount

返回字段：
- code
- message
- payment_status