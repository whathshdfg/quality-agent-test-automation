import type { TaskDraft } from '../types';

export const riskTagOptions = ['幂等性', '状态流转', '参数校验', '权限安全', '资源释放', '数据一致性', '并发操作'];

export const businessTypes = ['自动识别', '支付', '订单取消', '用户登录', '订单创建', '通用业务'];

export const examples: TaskDraft[] = [
  {
    name: '支付防重复扣款测试任务',
    businessType: '支付',
    riskTags: ['幂等性', '状态流转', '数据一致性'],
    requirement:
      '用户只能支付处于待支付状态的订单。支付成功后，订单状态更新为已支付并记录支付流水。用户重复支付时返回REPEAT_PAYMENT，并且不能发生重复扣款。',
  },
  {
    name: '订单取消资源释放测试任务',
    businessType: '订单取消',
    riskTags: ['状态流转', '资源释放', '幂等性'],
    requirement:
      '用户只能取消待接单或待服务状态的订单。订单取消后需要释放已占用资源。已完成订单不能取消，重复取消时不能重复退款和重复释放资源。',
  },
  {
    name: '账号登录安全测试任务',
    businessType: '用户登录',
    riskTags: ['参数校验', '权限安全'],
    requirement:
      '用户使用手机号和密码登录。手机号不能为空且必须符合格式要求。连续五次密码错误后账号锁定三十分钟，登录成功后清空登录失败次数。',
  },
  {
    name: '创建订单去重测试任务',
    businessType: '订单创建',
    riskTags: ['参数校验', '幂等性'],
    requirement:
      '用户提交起点、终点、联系人和预约时间后创建订单。起点和终点不能为空，预约时间不能早于当前时间。重复提交相同请求时只能生成一个订单。',
  },
];
