// Admission only: an in-progress driver call cannot be preempted to fit 2 ms.
#pragma once
#include <algorithm>
#include <chrono>
#include <thread>
#include <mutex>
namespace mkwvk::cache {
class TokenBucket {
public: using Clock = std::chrono::steady_clock;
private:
    double rate, tokens = 1.0;
    Clock::time_point previous;
public:
    explicit TokenBucket(double per_second, Clock::time_point now = Clock::now()) : rate(per_second), previous(now) {}
    bool try_take(Clock::time_point now) {
        if (rate <= 0) return true;
        if (now > previous) {
            tokens = std::min(1.0, tokens + std::chrono::duration<double>(now-previous).count()*rate);
            previous = now;
        }
        if (tokens < 1.0) return false;
        tokens -= 1.0; return true;
    }
    void take() {
        while (!try_take(Clock::now())) std::this_thread::sleep_for(std::chrono::duration<double>((1.0-tokens)/rate));
    }
};
class SharedTokenBucket {
    std::mutex mutex;
    TokenBucket bucket;
public:
    explicit SharedTokenBucket(double rate,TokenBucket::Clock::time_point now=TokenBucket::Clock::now()) : bucket(rate,now) {}
    bool try_take(TokenBucket::Clock::time_point now) {std::lock_guard lock(mutex);return bucket.try_take(now);}
    void take() {std::lock_guard lock(mutex);bucket.take();}
};
}
