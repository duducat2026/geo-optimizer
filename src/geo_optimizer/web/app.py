#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geo-web 启动器：GEO 多用户平台（Flask + MySQL）。

实际应用装配见 geo_optimizer.web.portal.app.create_app。
"""
import argparse
import logging

from geo_optimizer.web.portal.app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser(description="GEO 多用户平台")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=5000, help="监听端口")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    app = create_app()
    print("\n🌐 GEO 多用户平台启动中...")
    print(f"   地址: http://localhost:{args.port}")
    print("   默认管理员: admin / admin123")
    print("   按 Ctrl+C 停止\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
