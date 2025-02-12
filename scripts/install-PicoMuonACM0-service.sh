#!/bin/bash

echo "Start installing PicoMuonACM0 service..."

sudo cp -f ./PicoMuonACM0.service /etc/systemd/system
sudo chmod 644 /etc/systemd/system/PicoMuonACM0.service
sudo systemctl daemon-reload
sudo systemctl enable PicoMuonACM0.service
sudo systemctl start PicoMuonACM0.service

echo "PicoMuonACM0 service installed"