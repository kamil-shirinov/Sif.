// Optional local acceleration of the frozen simulator's valuation/margin arithmetic.
// No market data is written. Python builds actions and verifies against the original.
#include <algorithm>
#include <cmath>
#include <vector>

struct Action { int fill, earliest, pair, kind; };

extern "C" int simulate_stats(
    int n, int p, int r, int a, const int* usd_base, const double* full,
    const double* close_mid, const double* open_mid, const double* open_bid,
    const double* open_ask, const double* close_bid, const double* close_ask,
    const int* frames, const int* earliest, const int* action_pairs, const int* kinds,
    double equity0, double maintenance, double fraction, double* output) {
  if (n < 1 || p < 1 || r < 1) return 1;
  for (int trial = 0; trial < r; ++trial) {
    std::vector<double> qty(full, full+p), foreign(p);
    double usd = equity0;
    for (int j=0; j<p; ++j) {
      if (usd_base[j]) { usd += full[j]; foreign[j] = -full[j]*close_mid[j*n]; }
      else { foreign[j] = full[j]; usd -= full[j]*close_mid[j*n]; }
    }
    std::vector<Action> actions;
    for (int k=0; k<a; ++k) {
      int f = frames[trial*a+k];
      if (f > 0 && f < n) actions.push_back({f, earliest[trial*a+k], action_pairs[k], kinds[k]});
    }
    // Python orders pairs lexicographically in the quote matrix.
    std::stable_sort(actions.begin(), actions.end(), [](const Action& x, const Action& y) {
      if (x.fill != y.fill) return x.fill < y.fill;
      if (x.earliest != y.earliest) return x.earliest < y.earliest;
      if (x.pair != y.pair) return x.pair < y.pair;
      return x.kind < y.kind; // cut=0, restore=1
    });
    bool active = true;
    int mc=0, cuts=0, restores=0, fills=0;
    double costs=0, peak=-INFINITY, dd=0, ddpct=0, final_eq=equity0;
    size_t cursor=0;
    auto valuation = [&](const double* prices) {
      double eq=usd, gross=0;
      for (int j=0; j<p; ++j) {
        double price=prices[j];
        eq += foreign[j] * (usd_base[j] ? 1.0/price : price);
        gross += std::abs(qty[j]) * (usd_base[j] ? 1.0 : price);
      }
      return std::pair<double,double>(eq,gross);
    };
    auto trade = [&](int j, double target, const double* prices, const double* bids, const double* asks) {
      double dq=target-qty[j];
      if (dq==0) return;
      double price=dq>0 ? asks[j] : bids[j];
      if (usd_base[j]) { usd += dq; foreign[j] -= dq*price; }
      else { foreign[j] += dq; usd -= dq*price; }
      qty[j]=target;
      costs += std::abs(dq)*std::abs(price-prices[j]) * (usd_base[j] ? 1.0/prices[j] : 1.0);
      ++fills;
    };
    auto liquidate = [&](const double* prices, const double* bids, const double* asks) {
      for (int j=0; j<p; ++j) trade(j,0,prices,bids,asks);
      usd=valuation(prices).first;
      std::fill(foreign.begin(),foreign.end(),0);
      active=false; mc=1;
    };
    std::vector<double> po(p), pb(p), pa(p), pc(p), cb(p), ca(p);
    for (int i=0; i<n; ++i) {
      if (!active) break; // flat equity has no later drawdown or fill
      for (int j=0; j<p; ++j) {
        po[j]=open_mid[j*n+i]; pb[j]=open_bid[j*n+i]; pa[j]=open_ask[j*n+i];
        pc[j]=close_mid[j*n+i]; cb[j]=close_bid[j*n+i]; ca[j]=close_ask[j*n+i];
      }
      if (i>0) {
        auto v=valuation(po.data());
        if (v.second>0 && v.first<maintenance*v.second) liquidate(po.data(),pb.data(),pa.data());
        else {
          while (cursor<actions.size() && actions[cursor].fill==i) {
            const auto action=actions[cursor++]; int j=action.pair;
            if (action.kind==0 && qty[j]==full[j] && fraction>0) {
              trade(j,full[j]*(1-fraction),po.data(),pb.data(),pa.data()); ++cuts;
            } else if (action.kind==1 && qty[j]!=full[j]) {
              auto before=valuation(po.data());
              double dq=full[j]-qty[j], price=dq>0 ? pa[j] : pb[j];
              double cost=std::abs(dq)*std::abs(price-po[j]) * (usd_base[j] ? 1.0/po[j] : 1.0);
              double new_gross=before.second+(std::abs(full[j])-std::abs(qty[j])) * (usd_base[j] ? 1.0 : po[j]);
              if (before.first-cost >= maintenance*new_gross) {
                trade(j,full[j],po.data(),pb.data(),pa.data()); ++restores;
              }
            }
          }
        }
      }
      auto v=valuation(pc.data());
      if (active && v.second>0 && v.first<maintenance*v.second) liquidate(pc.data(),cb.data(),ca.data());
      final_eq=valuation(pc.data()).first;
      peak=std::max(peak,final_eq);
      dd=std::max(dd,peak-final_eq);
      ddpct=std::max(ddpct,peak>0 ? (peak-final_eq)/peak*100.0 : 0.0);
    }
    double* out=output+trial*9;
    out[0]=final_eq; out[1]=dd; out[2]=ddpct; out[3]=mc;
    out[4]=cuts; out[5]=restores; out[6]=costs; out[7]=fills; out[8]=usd;
  }
  return 0;
}
