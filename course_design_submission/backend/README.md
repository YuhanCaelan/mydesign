# 后端源码

FastAPI + SQLAlchemy 2.0 + PyMySQL + PyJWT，按 `controllers → services → mappers → models` 分层。

- Controller：接收参数、声明权限和返回结果。
- Service：处理排班冲突、号源生成、预约事务和状态流转。
- Mapper：封装数据库查询和分页。
- Model：维护 SQLAlchemy ORM 映射。

启动方式见交付目录中的《项目部署说明文档.md》。
