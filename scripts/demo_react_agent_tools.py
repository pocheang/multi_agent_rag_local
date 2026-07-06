"""
ReactAgent工具执行演示脚本

展示ReactAgent如何使用三个工具（vector_search, graph_query, web_search）
进行自主决策和迭代执行。

使用方法:
    python scripts/demo_react_agent_tools.py

或指定问题:
    python scripts/demo_react_agent_tools.py "Transformer的自注意力机制是什么？"
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.react_agent import ReactAgent, run_react_agent
from app.core.config import get_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_separator(title: str = "", char: str = "=", length: int = 80):
    """打印分隔线"""
    if title:
        padding = (length - len(title) - 2) // 2
        print(f"\n{char * padding} {title} {char * padding}")
    else:
        print(f"\n{char * length}")


def print_thought(iteration: int, thought: dict):
    """打印思考阶段"""
    print_separator(f"第{iteration}轮 - THINK阶段", "─")
    print(f"💭 思考: {thought.get('thought', 'N/A')}")
    print(f"🎯 行动: {thought.get('action', 'N/A')}")
    print(f"📝 输入: {thought.get('action_input', 'N/A')}")
    print(f"🧠 推理: {thought.get('reasoning', 'N/A')}")


def print_observation(observation: dict):
    """打印观察阶段"""
    print_separator("OBSERVE阶段", "─")
    print(f"🛠️  工具: {observation.get('tool', 'N/A')}")
    print(f"📊 结果: {observation.get('result', 'N/A')}")

    metadata = observation.get('metadata', {})
    if metadata:
        print(f"📈 元数据:")
        for key, value in metadata.items():
            print(f"   - {key}: {value}")


def print_final_result(result: dict):
    """打印最终结果"""
    print_separator("最终结果", "=")

    print(f"\n✅ 答案:")
    print(f"{result['answer']}\n")

    print(f"📊 统计信息:")
    print(f"   - 使用轮数: {result['iterations_used']}")
    print(f"   - 检测语言: {result['detected_language']}")

    # Vector结果统计
    vector_result = result.get('vector_result', {})
    if vector_result.get('retrieved_count', 0) > 0:
        print(f"\n📚 向量检索统计:")
        print(f"   - 检索总数: {vector_result['retrieved_count']}")
        print(f"   - 有效命中: {vector_result['effective_hit_count']}")
        print(f"   - 引用数量: {len(vector_result.get('citations', []))}")

    # Graph结果统计
    graph_result = result.get('graph_result', {})
    if graph_result.get('entities'):
        print(f"\n🕸️  图谱查询统计:")
        print(f"   - 实体数量: {len(graph_result['entities'])}")
        print(f"   - 关系数量: {len(graph_result.get('neighbors', []))}")

    # Web结果统计
    web_result = result.get('web_result', {})
    if web_result.get('used'):
        print(f"\n🌐 网络搜索统计:")
        print(f"   - 引用数量: {len(web_result.get('citations', []))}")


def print_history_summary(history: list):
    """打印执行历史摘要"""
    print_separator("执行历史摘要", "=")

    for i, step in enumerate(history, 1):
        thought = step['thought']
        action = thought['action']

        print(f"\n第{i}轮:")
        print(f"  动作: {action}")

        if action != 'finish':
            observation = step.get('observation')
            if observation:
                tool = observation['tool']
                metadata = observation.get('metadata', {})

                # 根据工具类型显示关键指标
                if tool == 'vector_search':
                    hits = metadata.get('retrieved_count', 0)
                    effective = metadata.get('effective_count', 0)
                    print(f"  结果: 检索{hits}个文档，{effective}个有效")
                elif tool == 'graph_query':
                    entities = metadata.get('entities_count', 0)
                    relations = metadata.get('relationships_count', 0)
                    print(f"  结果: {entities}个实体，{relations}个关系")
                elif tool == 'web_search':
                    citations = metadata.get('citations_count', 0)
                    print(f"  结果: {citations}个网络来源")


def demo_simple_question():
    """演示简单问题（预期2轮完成）"""
    print_separator("演示1: 简单概念问题", "=")

    question = "什么是Transformer模型？"
    print(f"\n❓ 问题: {question}")

    result = run_react_agent(
        question=question,
        max_iterations=5,
        use_reasoning=False,
    )

    # 打印执行过程
    for step in result['react_history']:
        print_thought(step['iteration'], step['thought'])

        if step['thought']['action'] != 'finish' and step.get('observation'):
            print_observation(step['observation'])

    print_history_summary(result['react_history'])
    print_final_result(result)


def demo_comparison_question():
    """演示对比问题（预期3-4轮完成）"""
    print_separator("演示2: 对比类问题", "=")

    question = "Transformer与RNN的主要区别是什么？"
    print(f"\n❓ 问题: {question}")

    result = run_react_agent(
        question=question,
        max_iterations=5,
        use_reasoning=False,
    )

    # 打印执行过程
    for step in result['react_history']:
        print_thought(step['iteration'], step['thought'])

        if step['thought']['action'] != 'finish' and step.get('observation'):
            print_observation(step['observation'])

    print_history_summary(result['react_history'])
    print_final_result(result)


def demo_multi_aspect_question():
    """演示多方面问题（预期使用多个工具）"""
    print_separator("演示3: 多方面问题", "=")

    question = "BERT模型的架构是什么？它在哪些任务上表现优异？有哪些实际应用案例？"
    print(f"\n❓ 问题: {question}")

    result = run_react_agent(
        question=question,
        max_iterations=5,
        use_reasoning=False,
    )

    # 打印执行过程
    for step in result['react_history']:
        print_thought(step['iteration'], step['thought'])

        if step['thought']['action'] != 'finish' and step.get('observation'):
            print_observation(step['observation'])

    print_history_summary(result['react_history'])
    print_final_result(result)


def demo_with_reasoning_model():
    """演示使用推理模型（更强的思考能力）"""
    print_separator("演示4: 使用推理模型", "=")

    question = "请详细对比Transformer、LSTM和GRU三种模型的优缺点"
    print(f"\n❓ 问题: {question}")

    result = run_react_agent(
        question=question,
        max_iterations=5,
        use_reasoning=True,  # 启用推理模型
    )

    # 打印执行过程
    for step in result['react_history']:
        print_thought(step['iteration'], step['thought'])

        if step['thought']['action'] != 'finish' and step.get('observation'):
            print_observation(step['observation'])

    print_history_summary(result['react_history'])
    print_final_result(result)


def demo_custom_question(question: str):
    """演示自定义问题"""
    print_separator("自定义问题演示", "=")
    print(f"\n❓ 问题: {question}")

    result = run_react_agent(
        question=question,
        max_iterations=5,
        use_reasoning=False,
    )

    # 打印执行过程
    for step in result['react_history']:
        print_thought(step['iteration'], step['iteration'])

        if step['thought']['action'] != 'finish' and step.get('observation'):
            print_observation(step['observation'])

    print_history_summary(result['react_history'])
    print_final_result(result)


def export_result_to_json(result: dict, filename: str = "react_agent_demo_result.json"):
    """将结果导出为JSON文件"""
    output_path = Path(__file__).parent.parent / "logs" / filename
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已导出到: {output_path}")


def main():
    """主函数"""
    print_separator("ReactAgent工具执行演示", "=")
    print("\n这个脚本演示ReactAgent如何自主使用工具:")
    print("  🔍 vector_search - 向量检索本地文档")
    print("  🕸️  graph_query - 查询知识图谱")
    print("  🌐 web_search - 搜索互联网")
    print("  ✅ finish - 信息充足时结束\n")

    # 检查环境配置
    try:
        settings = get_settings()
        print(f"✅ 环境配置加载成功")
        print(f"   - 向量库: {settings.chroma_persist_directory}")
        print(f"   - 模型: {settings.openai_model or 'default'}")
    except Exception as e:
        print(f"❌ 环境配置加载失败: {e}")
        print("   请确保已配置 .env 文件")
        return

    # 如果命令行提供了问题，只运行自定义问题
    if len(sys.argv) > 1:
        custom_question = " ".join(sys.argv[1:])
        demo_custom_question(custom_question)
        return

    # 运行预设演示
    demos = [
        ("简单概念问题", demo_simple_question),
        ("对比类问题", demo_comparison_question),
        ("多方面问题", demo_multi_aspect_question),
        ("使用推理模型", demo_with_reasoning_model),
    ]

    print("\n可用演示:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    print(f"  0. 运行所有演示")
    print(f"  q. 退出")

    while True:
        try:
            choice = input("\n请选择演示编号 (0-4, q退出): ").strip().lower()

            if choice == 'q':
                print("👋 退出演示")
                break

            if choice == '0':
                # 运行所有演示
                for name, demo_func in demos:
                    print(f"\n{'='*80}")
                    print(f"运行演示: {name}")
                    print(f"{'='*80}")
                    try:
                        demo_func()
                    except KeyboardInterrupt:
                        print("\n⚠️  演示被用户中断")
                        break
                    except Exception as e:
                        logger.exception(f"演示失败: {e}")
                        print(f"\n❌ 演示失败: {e}")
                break

            idx = int(choice)
            if 1 <= idx <= len(demos):
                name, demo_func = demos[idx - 1]
                print(f"\n{'='*80}")
                print(f"运行演示: {name}")
                print(f"{'='*80}")
                try:
                    demo_func()
                except KeyboardInterrupt:
                    print("\n⚠️  演示被用户中断")
                    break
                except Exception as e:
                    logger.exception(f"演示失败: {e}")
                    print(f"\n❌ 演示失败: {e}")
            else:
                print("❌ 无效选择，请输入0-4或q")

        except ValueError:
            print("❌ 请输入有效数字")
        except KeyboardInterrupt:
            print("\n👋 退出演示")
            break
        except Exception as e:
            logger.exception(f"发生错误: {e}")
            print(f"\n❌ 发生错误: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序被用户中断")
    except Exception as e:
        logger.exception(f"程序异常退出: {e}")
        print(f"\n❌ 程序异常退出: {e}")
