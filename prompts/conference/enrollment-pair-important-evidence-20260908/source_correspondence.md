# 同会话针对性复核：原件字段对应不等于事实采信

延续当前只读审阅角色和同一模型，不另起其他节点。允许新增读取的文件见context/enrollment-pair-important-evidence-20260908_conference_context.md的source_correspondence补充；其余边界不变。不要读取个人配置、工作流命令文件、其他报告、密钥，不写任何文件、不调用外部API。

请重新目视原图artifacts/phase55-model-comparison/20260907/product-source-d001-sa07007-v1/pages/f5159a54ff8c596e6f95eaa791bc92a412d833a3acaaf1466930656b2b7348ac，独立核对同根alignment-mlx-d00142-20260908/posthoc-source-correspondence.json的14项字段对应标注。该标注是主线程在模型输出之后做的，不是既定权威，不能因为给出了配对便默认正确。

同时读page-0.json中的两主读观察和实际模型配对、scripts/evaluate_observation_alignment.py的提示与检查，回答：
1. 哪些ID对确实指向同一原件字段，哪些证据不足？这是位置/字段对应，不是数值正确、事件同一或临床采信。
2. 单页事后金标能否支持12个提议正确、漏2个的限定计数？如不能请具体指出，不评价整体模型优劣。
3. 严格提示要求双方明确事件时间但人口学字段、日期字段本身的context.time_text为空：应如何区分提示遵循、观察对应及事实核实三种验收？不授权删掉时间约束。
4. 若下一轮仅在隔离测试改进，最小且可证伪的正反例是什么？必须覆盖同页多日期/多目标、同数字异项目、结果与参考范围、备注与结论、来源本身冲突。不要直接设计新巨大系统，不自行宣布通过。

返回中文审阅，明确实际看图情况、具体ID与不确定性，最多约120行。不要复述整个既有横评。runner负责保存，不自行写文件。
